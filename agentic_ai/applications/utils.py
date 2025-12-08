"""  
Key-value state-store utilities.  
  
Document schema  
---------------  
{  
    "id"        : "<session_id>",   # required by Cosmos  
    "tenant_id" : "<tenant_id>",    # application tenant (defaults to "default")  
    "value"     : <JSON-serialisable python object>  
}  
  
Partition-key  
-------------  
Hierarchical / multi-hash on                /tenant_id  +  /id  
"""  
  
from __future__ import annotations  
  
import json  
import os  
import logging  
import collections.abc as abc  
from typing import Any, Dict, Iterator, List, Optional  
from datetime import datetime  

# ---------------------------------------------------------------------------  
# 3rd-party SDKs  
# ---------------------------------------------------------------------------  
try:  
    from azure.cosmos import (  
        CosmosClient,  
        PartitionKey,  
        exceptions as cosmos_exceptions,  
    )  
except ImportError:  
    CosmosClient = None  # type: ignore  
  
try:  
    from azure.identity import ClientSecretCredential, DefaultAzureCredential  
except ImportError:  
    ClientSecretCredential = DefaultAzureCredential = None  # type: ignore  

  
def make_json_serializable(obj):  
    if isinstance(obj, dict):  
        return {k: make_json_serializable(v) for k, v in obj.items()}  
    elif isinstance(obj, list):  
        return [make_json_serializable(i) for i in obj]  
    elif isinstance(obj, datetime):  
        return obj.isoformat()  
    else:  
        return obj  
# ---------------------------------------------------------------------------  
# Cosmos-backed implementation  
# ---------------------------------------------------------------------------  
class CosmosDBStateStore(abc.MutableMapping):  
    """  
    Dict-like wrapper around a Cosmos DB container whose hierarchical  
    partition key is (tenant_id, id).  
  
    Keys   -> session_id  
    Values -> arbitrary JSON-serialisable python objects  
    """  
  
    def __init__(self) -> None:  
        if CosmosClient is None:  
            raise RuntimeError("azure-cosmos is not installed")  
  
        endpoint = os.getenv("COSMOSDB_ENDPOINT") or os.getenv("COSMOS_DB_ENDPOINT")  
        if not endpoint:  
            raise RuntimeError("COSMOSDB_ENDPOINT must be defined")  
  
        # Data-level tenant (NOT the AAD tenant used for auth)  
        self.tenant_id: str = os.getenv("DATA_TENANT_ID", "default")  
  
        self.client = CosmosClient(endpoint, credential=self._create_credential())  
  
        db_name = (  
            os.getenv("COSMOSDB_DB_NAME")  
            or os.getenv("COSMOS_DB_NAME")  
            or "ai_state_db"  
        )  
        container_name = (  
            os.getenv("COSMOSDB_CONTAINER_NAME")  
            or os.getenv("COSMOS_CONTAINER_NAME")  
            or "state_store"  
        )  
  
        # Partition key: /tenant_id  +  /id  
        pk = PartitionKey(path=["/tenant_id", "/id"], kind="MultiHash")  
  
        self.database = self.client.create_database_if_not_exists(id=db_name)  
        self.container = self.database.create_container_if_not_exists(  
            id=container_name,  
            partition_key=pk,  
        )  
  
    # ------------------------- authentication helpers -------------------------  
    def _create_credential(self):  
        key = os.getenv("COSMOSDB_KEY")  
        if key:  
            logging.info("CosmosDBStateStore: authenticating with KEY")  
            return key  
  
        c_id, c_secret, t_id = (  
            os.getenv("AAD_CLIENT_ID"),  
            os.getenv("AAD_CLIENT_SECRET"),  
            os.getenv("AAD_TENANT_ID"),  
        )  
        if c_id and c_secret and t_id:  
            if ClientSecretCredential is None:  
                raise RuntimeError("azure-identity is not installed")  
            logging.info("CosmosDBStateStore: authenticating with AAD client-secret")  
            return ClientSecretCredential(  
                tenant_id=t_id, client_id=c_id, client_secret=c_secret  
            )  
  
        if DefaultAzureCredential is None:  
            raise RuntimeError(  
                "No Cosmos key or AAD creds found, and azure-identity is missing."  
            )  
        logging.info("CosmosDBStateStore: authenticating with DefaultAzureCredential")  
        return DefaultAzureCredential(exclude_interactive_browser_credential=True)  
  
    # ------------------------- internal helpers -------------------------  
    def _read(self, session_id: str) -> Optional[Dict[str, Any]]:  
        try:  
            return self.container.read_item(  
                item=session_id,  
                partition_key=[self.tenant_id, session_id],  
            )  
        except cosmos_exceptions.CosmosResourceNotFoundError:  
            return None  
  
    # ------------------------- MutableMapping API -------------------------  
    def __getitem__(self, session_id: str) -> Any:  
        doc = self._read(session_id)  
        if doc is None:  
            raise KeyError(session_id)  
        return doc["value"]  
  
    def get(self, session_id: str, default: Any = None):  # type: ignore[override]  
        doc = self._read(session_id)  
        return default if doc is None else doc["value"]  
  
    def __setitem__(self, session_id: str, value: Any) -> None:  
        self.container.upsert_item(  
            {  
                "id": session_id,          # unique within a tenant  
                "tenant_id": self.tenant_id,  
                "value": value,  
            }  
        )  
  
    def __delitem__(self, session_id: str) -> None:  
        try:  
            self.container.delete_item(  
                item=session_id,  
                partition_key=[self.tenant_id, session_id],  
            )  
        except cosmos_exceptions.CosmosResourceNotFoundError:  
            raise KeyError(session_id)  
  
    def __iter__(self) -> Iterator[str]:  
        query = "SELECT c.id FROM c WHERE c.tenant_id = @tid"  
        for doc in self.container.query_items(  
            query=query,  
            parameters=[{"name": "@tid", "value": self.tenant_id}],  
            enable_cross_partition_query=True,  
        ):  
            yield doc["id"]  
  
    def __len__(self) -> int:  
        query = "SELECT VALUE COUNT(1) FROM c WHERE c.tenant_id = @tid"  
        res: List[int] = list(  
            self.container.query_items(  
                query=query,  
                parameters=[{"name": "@tid", "value": self.tenant_id}],  
                enable_cross_partition_query=True,  
            )  
        )  
        return res[0] if res else 0  
  
  
# ---------------------------------------------------------------------------  
# public factory  
# ---------------------------------------------------------------------------  
def get_state_store() -> Dict[str, Any] | CosmosDBStateStore:  
    """  
    Return a CosmosDBStateStore if Cosmos configuration exists, else a dict.  
    """  
    have_endpoint = os.getenv("COSMOSDB_ENDPOINT") or os.getenv("COSMOS_DB_ENDPOINT")  
    have_key = os.getenv("COSMOSDB_KEY")  
    have_aad = (  
        os.getenv("AAD_CLIENT_ID")  
        and os.getenv("AAD_CLIENT_SECRET")  
        and os.getenv("AAD_TENANT_ID")  
    )  
  
    if have_endpoint and (have_key or have_aad):  
        logging.info("Using Cosmos DB state store (tenant_id + id partition)")  
        return CosmosDBStateStore()  
  
    logging.info("Cosmos DB config absent → using in-memory dict")  
    return {}  # fallback  