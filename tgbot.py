import os
import json
import openai
import logging
from telegram import Update, ForceReply
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, BaseFilter

# Load your OpenAI API key and Telegram token
openai.api_key = os.environ["OPENAI_API_KEY"]
telegram_token = os.environ["TELEGRAM_TOKEN"]

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
logging.basicConfig(level=logging.INFO)

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
class AllowedChatIDFilter:
    def __call__(self, update: Update):
        return update.message and update.message.chat_id in allowed_chat_ids

dispatcher.add_handler(MessageHandler((Filters.text & ~Filters.command) & AllowedChatIDFilter(), chat_with_gpt))

# Start the Bot
updater.start_polling()
updater.idle()
