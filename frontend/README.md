# Frontend - CryptoBot Dashboard

Modern React dashboard for the CryptoBot trading application.

## Tech Stack

- **Next.js 14** - React framework with App Router
- **Tailwind CSS** - Utility-first CSS
- **React Query** - Data fetching and caching
- **TypeScript** - Type safety

## Getting Started

1. Install dependencies:
```bash
npm install
```

2. Create `.env.local`:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

3. Run development server:
```bash
npm run dev
```

4. Open [http://localhost:3000](http://localhost:3000)

## Build for Production

```bash
npm run build
npm start
```

## Docker

```bash
docker build -t cryptobot-frontend .
docker run -p 3000:3000 cryptobot-frontend
```
