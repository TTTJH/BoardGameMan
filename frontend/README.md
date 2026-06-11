# Frontend Setup Instructions

## Prerequisites
- Node.js 16 or higher
- npm or yarn package manager

## Installation Steps

### 1. Install Dependencies
```bash
npm install
```

### 2. Development Server
```bash
npm run dev
```

The application will be available at `http://localhost:3000`

### 3. Build for Production
```bash
npm run build
```

Output will be in the `dist/` directory.

### 4. Preview Production Build
```bash
npm run preview
```

## Project Structure

- `src/App.jsx` - Main application component
- `src/components/` - React components
- `src/store/` - Zustand state management
- `src/api/` - API client
- `src/index.css` - Global styles
- `vite.config.js` - Vite configuration
- `tailwind.config.js` - Tailwind CSS configuration

## Key Components

- **GameList** - Display and manage board games
- **GameDetail** - Game details with document upload and chat
- **DocumentUpload** - PDF file upload interface
- **ChatBox** - Q&A chat interface

## State Management

Using Zustand for state management:
- `useGameStore` - Game data
- `useChatStore` - Chat messages
- `useDocumentStore` - Document data

## API Integration

API client in `src/api/client.js`:
- `gamesAPI` - Game management endpoints
- `documentsAPI` - Document upload endpoints
- `chatAPI` - Chat and Q&A endpoints

## Styling

- Tailwind CSS for utility-first styling
- Custom CSS classes in `src/index.css`
- Responsive design with mobile-first approach

## Troubleshooting

### Port Already in Use
Change the port in `vite.config.js` or kill the process using port 3000.

### API Connection Issues
Check that the backend is running and the proxy configuration in `vite.config.js` is correct.

### Build Errors
Clear `node_modules` and `dist` directories, then run `npm install` again.
