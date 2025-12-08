# Magentic AI Chat - React Frontend

Professional React frontend for multi-agent AI assistant with real-time streaming.

## Features

- 🎨 **Clean Split UI**: Chat on the right, internal process on the left
- 📊 **Real-time Streaming**: See orchestrator planning and agent work live
- 🎯 **Collapsible Sections**: Expand/collapse orchestrator and individual agents
- 🎭 **Material-UI**: Professional, responsive design
- 🔄 **WebSocket**: Low-latency real-time updates
- 👁️ **Toggle Process View**: Show/hide internal thinking

## Setup

1. Install dependencies:
```bash
cd react-frontend
npm install
```

2. Configure backend URL (optional):
Create `.env` file:
```
REACT_APP_BACKEND_URL=http://localhost:7000
```

3. Start the development server:
```bash
npm start
```

The app will open at http://localhost:3000

## Usage

1. Type your question in the input box
2. Press Enter or click Send
3. Watch the internal process on the left (orchestrator planning, agents working)
4. See the final answer in the main chat area
5. Click the eye icon to hide/show the internal process panel

## Production Build

```bash
npm run build
```

Serves the optimized production build from the `build/` directory.
