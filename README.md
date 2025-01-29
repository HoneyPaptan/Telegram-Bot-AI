# Telegram AI Chatbot

A Telegram chatbot powered by Gemini AI, MongoDB, and SerpAPI. This bot allows users to register, interact with Gemini for chat and image/file analysis, and perform web searches with AI-generated summaries.

## Features

1. **User Registration**  
   - Saves `first_name`, `username`, `chat_id`, and phone number in MongoDB.
   - Sends a confirmation message after registration.

2. **Gemini-Powered Chat**  
   - Uses Gemini API to answer user queries.
   - Stores full chat history (user input + bot response) in MongoDB with timestamps.

3. **Image/File Analysis**  
   - Accepts images/files (JPG, PNG, PDF) and uses Gemini to describe their content.
   - Saves file metadata (filename, description) in MongoDB.

4. **Web Search**  
   - Allows users to perform web searches using `/websearch`.
   - Returns an AI summary of search results with top web links using SerpAPI.

## Setup Instructions

### Prerequisites
- Python 3.8 or higher
- Telegram Bot Token (from [BotFather](https://core.telegram.org/bots#botfather))
- Gemini API Key (from [Google AI Studio](https://aistudio.google.com/))
- MongoDB Connection URI (from [MongoDB Atlas](https://www.mongodb.com/cloud/atlas))
- SerpAPI Key (from [SerpAPI](https://serpapi.com/))

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/telegram-ai-chatbot.git
   cd telegram-ai-chatbot
