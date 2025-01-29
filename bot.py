import google.generativeai as genai
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from pymongo import MongoClient
import re
from datetime import datetime, UTC 
import requests
from urllib.parse import quote_plus
from dotenv import load_dotenv
import os


load_dotenv() 

# MongoDB connection details
MONGO_URI =  os.getenv("MONGODB_URI")
client = MongoClient(MONGO_URI)
db = client["telegrambot"]  # Replace with your database name
users_collection = db["users"]
chat_collection = db["chat_history"]
files_collection = db["file_metadata"]






# Set up Gemini AI
GEMINI_API_KEY = os.getenv("GOOGE_GEMINI_KEY")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# /start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user:
        user_data = {
            "chat_id": user.id,
            "first_name": user.first_name,
            "username": user.username,
        }
        # Insert or update user in MongoDB
        users_collection.update_one(
            {"chat_id": user.id}, {"$set": user_data}, upsert=True
        )

        # Create a "Share Phone Number" button
        keyboard = [[KeyboardButton("📱 Share Phone Number", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

        await update.message.reply_text(
            f"Welcome, {user.first_name}! Please share your phone number.",
            reply_markup=reply_markup
        )

# Handle phone number response
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    if contact:
        # Update user document with phone number
        users_collection.update_one(
            {"chat_id": contact.user_id}, {"$set": {"phone_number": contact.phone_number}}
        )
        await update.message.reply_text("✅ Phone number saved successfully!")

def format_response(text: str) -> str:
    """
    Preserves intended markdown formatting while escaping special characters
    Handles both MarkdownV2 and automatic formatting cleanup
    """
    # First escape all special characters properly
    safe_text = escape_markdown(text, version=2)
    
    # Then selectively unescape common formatting patterns
    formatting_patterns = {
        r'\\\*': '*',  # Unescape bold/italic
        r'\\\_': '_',  # Unescape underline
        r'\\\[': '[',  # Unescape links
        r'\\\]': ']'
    }
    
    for pattern, replacement in formatting_patterns.items():
        safe_text = re.sub(pattern, replacement, safe_text)
        
    return safe_text

# Function to get AI response
def get_ai_response(user_input):
    try:
        response = model.generate_content(user_input)
        return response.text.strip() if response else "I couldn't generate a response."
    except Exception as e:
        return f"Error: {str(e)}"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    chat_id = update.message.chat_id

     # Get AI response
    ai_response = get_ai_response(user_message)

    # Format Markdown properly
    formatted_response = format_response(ai_response)

    # Store chat history in MongoDB
    chat_data = {
        "chat_id": chat_id,
        "user_message": user_message,
        "bot_response": ai_response,
    }
    chat_collection.insert_one(chat_data)

     # Send properly styled message
    await update.message.reply_text(
        formatted_response,
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def analyze_with_gemini(file_data, mime_type):
    """
    Sends the file data to Gemini AI and retrieves a description.
    """
    # Add text prompt based on file type
    if mime_type.startswith('image/'):
        prompt = "Analyze this image and describe its content with metadata."
    else:
        prompt = "Analyze this document and describe its content with metadata."

    response = model.generate_content(
        [
            prompt,  # Text parameter
            {
                "mime_type": mime_type,
                "data": file_data
            }
        ]
    )
    return response.text if response else "No description available."
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles incoming files (images, PDFs, etc.), analyzes with Gemini, and saves metadata.
    """
    file = update.message.document or update.message.photo[-1]  # Handle both documents & images
    file_id = file.file_id
    file_info = await context.bot.get_file(file_id)
    
    # Get file data directly as bytes
    file_data = bytes(await file_info.download_as_bytearray())
    
    # Determine file name and MIME type
    file_name = file.file_name if hasattr(file, 'file_name') else f"{file_id}.jpg"
    mime_type = file.mime_type if hasattr(file, 'mime_type') else "image/jpeg"

    # Analyze with Gemini
    description = await analyze_with_gemini(file_data, mime_type)

    # Store metadata in MongoDB
    metadata = {
        "file_name": file_name,
        "file_type": mime_type,
        "description": description,
        "uploaded_at": datetime.now(UTC),  # Instead of utcnow()
    }
    files_collection.insert_one(metadata)

    raw_response = f"📁 File Received: {file_name}\n📄 Description: {description}"
    formatted_response = format_response(raw_response)
    await update.message.reply_text(formatted_response, parse_mode=ParseMode.MARKDOWN_V2)


async def websearch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /websearch command with AI-powered web results"""
    try:
        # Get search query
        query = " ".join(context.args).strip()
        if not query:
            await update.message.reply_text("🔍 Please enter a search query after /websearch")
            return

        # Show typing indicator
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, 
            action="typing"
        )

        # Perform web search
        params = {
            "q": query,
            "api_key": os.getenv("SERPAPI_KEY"),
            "engine": "google",
            "num": 3  # Get top 3 results
        }
        response = requests.get("https://serpapi.com/search", params=params)
        results = response.json()

        # Process results with Gemini
        if "organic_results" in results:
            search_content = "\n".join(
                [f"{i+1}. {res['title']}\n   {res['link']}\n   {res.get('snippet', '')}"
                 for i, res in enumerate(results["organic_results"][:3])]
            )
            
            # Generate AI summary
            prompt = f"""Analyze these web search results and provide a concise summary:
            {search_content}
            
            Include 3 most relevant links. Format response for Telegram with proper MarkdownV2 escaping."""
            
            ai_response = model.generate_content(prompt)
            summary = ai_response.text if ai_response else "Could not generate summary"
            
            # Format response
            formatted_response = format_response(
                f"🔍 *Web Search Results for* '{query}':\n\n{summary}"
            )
            
            await update.message.reply_text(
                formatted_response,
                parse_mode=ParseMode.MARKDOWN_V2,
                disable_web_page_preview=True
            )
        else:
            await update.message.reply_text("❌ No results found for your search query")

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error performing search: {str(e)}")

# Add this new command handler
async def sentiment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Analyze message sentiment using Gemini"""
    try:
        # Get text from message or replied message
        text = update.message.reply_to_message.text if update.message.reply_to_message else " ".join(context.args)
        
        if not text:
            await update.message.reply_text("💡 Please reply to a message or provide text after /sentiment")
            return

        # Generate sentiment analysis
        prompt = f"""Analyze this text's sentiment with:
        1. Primary emotion (e.g., happy, angry)
        2. Sentiment score (-1 to 1)
        3. Confidence level (0-100%)
        Format as: Emotion|Score|Confidence
        
        Text: {text}"""
        
        response = model.generate_content(prompt)
        if not response.text:
            await update.message.reply_text("❄️ Couldn't analyze sentiment")
            return

        # Parse response
        parts = response.text.split("|")
        if len(parts) != 3:
            await update.message.reply_text(f"📊 Sentiment: {response.text}")
            return

        emotion, score, confidence = parts
        formatted = f"""
        🧠 *Sentiment Analysis*:
        🔮 Emotion: {emotion.strip()}
        📈 Score: {score.strip()}
        💯 Confidence: {confidence.strip()}
        """
        await update.message.reply_text(
            format_response(formatted),
            parse_mode=ParseMode.MARKDOWN_V2
        )

    except Exception as e:
        await update.message.reply_text(f"⚠️ Analysis failed: {str(e)}")



def main():
    # Create the bot application
    application = Application.builder().token("7898139526:AAFQ38G79MbxuY91vEM9Q-B6eIcGprnwydw").build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))

    # Handle contact sharing (phone number)
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))

    # Handle user messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Handle files
    application.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file))

    application.add_handler(CommandHandler("websearch", websearch))

    application.add_handler(CommandHandler("sentiment", sentiment))



    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()