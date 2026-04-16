# Project

A Node.js application using OpenAI API.

## Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Create a `.env.local` file based on `.env.example`:
   ```bash
   cp .env.example .env.local
   ```

3. Add your OpenAI API key to `.env.local`

4. Run the application:
   ```bash
   node server.js
   ```

## Environment Variables

- `OPENAI_API_KEY` - Your OpenAI API key (required)

## Security

Never commit `.env.local` or other environment files with sensitive data. Always use `.env.example` as a template.
