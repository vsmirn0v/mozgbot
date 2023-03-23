import os
import json
import openai
import logging
import time
from telegram import Update, ForceReply
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, BaseFilter, MessageFilter
class AllowedChatIDFilter(MessageFilter):
    def filter(self, message):
        return message.chat_id in allowed_chat_ids
    
# Load your OpenAI API key and Telegram token
openai.api_key = os.environ["OPENAI_API_KEY"]
telegram_token = os.environ["TELEGRAM_TOKEN"]
allowed_chat_ids = os.environ["TELEGRAM_CHAT_IDS"]
TELEGRAM_CHAT_IDS = os.environ.get("TELEGRAM_CHAT_IDS", "")
allowed_chat_ids = [int(chat_id.strip()) for chat_id in TELEGRAM_CHAT_IDS.split(",") if chat_id.strip()]

# Load the training prompts from a JSON configuration file
with open("training_prompts.json", "r") as f:
    training_prompts = json.load(f)

# Load the conversation history from a file if it exists, otherwise create an empty dictionary
try:
    with open("conversation_history.json", "r") as f:
        conversation_history = json.load(f)
except FileNotFoundError:
    conversation_history = {}

# Save the conversation history to a file
def save_conversation_history():
    with open("conversation_history.json", "w") as f:
        json.dump(conversation_history, f)

# Set up logging
logging.basicConfig(level=logging.WARN, format='%(asctime)s - %(levelname)s - %(message)s')

def unauthorized_chat(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    message_text = update.message.text
    logging.info(f"Unauthorized access: User ID: {user_id}, Message: {message_text}")
    update.message.reply_text("Доступ запрещен.")
    
class UnauthorizedChatIDFilter(MessageFilter):
    def filter(self, message):
        return message.chat_id not in allowed_chat_ids

unauthorized_chat_ids_filter = UnauthorizedChatIDFilter()

def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Хола человеки! Чем я могу помочь вам сегодня?")

def chat_with_gpt(update: Update, context: CallbackContext) -> None:
    if update.channel_post:  # Check if the update comes from a channel
        user_message = update.channel
        user_message = update.channel_post.text
        chat_id = update.channel_post.chat.id
    else:
        user_message = update.message.text
        chat_id = update.message.chat.id

    # Retrieve conversation history or create an empty history
    history = conversation_history.get(str(chat_id), "")

    # Add user message to the conversation history
    history += f"User: {user_message}\nAI: "

    # Record the start time
    start_time = time.perf_counter()
    
    # GPT-related code
    openai_response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=(f"{training_prompts}\n{history}"),
        max_tokens=150,
        n=1,
        stop=None,
        temperature=0.5,
    )

    response = openai_response.choices[0].text.strip()
    
    elapsed_time = time.perf_counter() - start_time
    
    tokens_used = openai_response.get("usage", {}).get("total_tokens", 0)
    
    logging.warn(f"Incoming message: User ID: {user_id}, Chat ID: {chat_id}, Time consumed: {elapsed_time:.2f} seconds, Tokens consumed: {tokens_used}, Message: {message_text}")

    # Add AI response to the conversation history
    history += f"{response}\n"

    # Update conversation history for the user or channel
    conversation_history[str(chat_id)] = history
    save_conversation_history()

    if update.channel_post:
        context.bot.send_message(chat_id=update.channel_post.chat.id, text=response)
    else:
        update.message.reply_text(response)

# Create the Updater and pass your bot's token
updater = Updater(telegram_token)

# Get the dispatcher to register handlers
dispatcher = updater.dispatcher

# Add handlers
dispatcher.add_handler(CommandHandler("start", start))
allowed_chat_ids_filter = AllowedChatIDFilter()

dispatcher.add_handler(MessageHandler((Filters.text & ~Filters.command) & unauthorized_chat_ids_filter, unauthorized_chat))
dispatcher.add_handler(MessageHandler((Filters.text & ~Filters.command) & allowed_chat_ids_filter, chat_with_gpt))

# Start the Bot
updater.start_polling()
updater.idle()
