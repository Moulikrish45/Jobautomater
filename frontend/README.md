# Job Application Dashboard

React frontend for the Job Application Automation Platform.

## Features

- **Dashboard**: Overview of application metrics and trends
- **Applications**: View and manage job applications with filtering
- **Job Queue**: Monitor jobs queued for application
- **Settings**: Control automation settings and system configuration

## Getting Started

### Prerequisites

- Node.js 16+ 
- npm or yarn

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm start
```

The application will be available at `http://localhost:3000`.

### Building for Production

```bash
npm run build
```

## Project Structure

```
src/
├── components/          # Reusable UI components
├── pages/              # Main page components
├── services/           # API service layer
├── types/              # TypeScript type definitions
├── App.tsx             # Main application component
└── index.tsx           # Application entry point
```

## API Integration

The frontend communicates with the FastAPI backend at `http://localhost:8000/api/v1/`.

Key API endpoints:
- `/dashboard/users/{user_id}/applications` - Get user applications
- `/dashboard/users/{user_id}/metrics` - Get dashboard metrics
- `/dashboard/users/{user_id}/trends` - Get application trends
- `/dashboard/users/{user_id}/jobs/queue` - Get job queue

## Technologies Used

- **React 18** with TypeScript
- **Material-UI (MUI)** for UI components
- **React Router** for navigation
- **Recharts** for data visualization
- **Axios** for API communication
- **date-fns** for date formatting