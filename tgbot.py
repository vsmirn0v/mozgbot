import os
import json
import openai
import logging
import time
from telegram import Update, ForceReply
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, BaseFilter, MessageFilter

class IsReplyFilter(MessageFilter):
    def filter(self, message):
        return message.reply_to_message is not None

class AllowedChatIDFilter(MessageFilter):
    def filter(self, message):
        return message.chat_id in allowed_chat_ids

class BotNameFilter(MessageFilter):
    def __init__(self, bot_names):
        self.bot_names = bot_names

    def filter(self, message):
        return any(bot_name.lower() in message.text.lower() for bot_name in self.bot_names)

def send_still_processing(context: CallbackContext):
    """Sends a 'still processing' message to the chat."""
    job = context.job
    context.bot.send_message(chat_id=job.context["chat_id"], text="Ещё думаю... 🧠")


# Replace with your desired bot names
bot_names = ["гарсон", "garcon", "garcón", "garcon_devops_bot"]

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

def unauthorized_chat(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    user_name = update.message.from_user.name
    chat_id = update.message.chat_id
    chat_name = update.message.chat.title
    message_text = update.message.text
    logging.info(f"Unauthorized access: User: {user_name}, Chat: {chat_name}, Chat ID: {chat_id}, Message: {message_text}")
    update.message.reply_text("Доступ запрещен.")
    
class UnauthorizedChatIDFilter(MessageFilter):
    def filter(self, message):
        return message.chat_id not in allowed_chat_ids

unauthorized_chat_ids_filter = UnauthorizedChatIDFilter()

def start(update: Update, context: CallbackContext) -> None:
    chat_name = update.message.chat.title

    update.message.reply_text(f"Хола, человеки\! Меня зовут Гарсон и я здесь, чтобы ~захватить мир~ сделать вашу жинзь чуточку проще\.",parse_mode='MarkdownV2')
    update.message.reply_text(f"Я отвечаю только на прямые обращения по моему имени гарсон, garcon или garcon_devops_bot. А так же отвечаю на ответы на мои сообщения.")
    update.message.reply_text(f"Чем я могу помочь вам сегодня?")

    logging.info(f"Start initiated from chat_id: {chat_name}")
    
def log_incoming_message(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    user_name = update.message.from_user.name
    chat_id = update.message.chat_id
    chat_name = update.message.chat.title
    message_text = update.message.text
    logging.info(f"Incoming message: User: {user_name}, Chat: {chat_name}, Message: {message_text}")

def chat_with_gpt(update: Update, context: CallbackContext) -> None:
    if update.channel_post:  # Check if the update comes from a channel
        user_message = update.channel
        user_message = update.channel_post.text
        chat_id = update.channel_post.chat.id
    else:
        user_message = update.message.text
        chat_id = update.message.chat.id

    chat_name = update.message.chat.title
    user_name = update.message.from_user.name
    reply_to_message = update.message.reply_to_message
    is_reply = reply_to_message and reply_to_message.from_user.id == context.bot.id
 
    user_id = update.message.from_user.id

    if not (any(bot_name.lower() in user_message.lower() for bot_name in bot_names) or is_reply):
        logging.info(f"Reply to other user message. Discarding.")
        return False

    logging.info(f"Request: User: {user_name}, Chat: {chat_name}, Is reply: {is_reply}, Message: {user_message}")

    # Retrieve conversation history or create an empty history
    history = conversation_history.get(str(chat_id), "[]")
    if not isinstance(history, list):
        history = []

    # Add user message to the conversation historyf
    #history += f"{user_name}: {user_message}\nAI: "

    history = history + [{"role": "user", "content": f"{user_name}: {user_message}"}]

    # Record the start time
    start_time = time.perf_counter()
    
    # GPT-related code
    openai_params = {}
    openai_params["model"] = "gpt-3.5-turbo"
    openai_params["messages"] = training_prompts + history
    #openai_params["max_tokens"] = 1024
    #openai_params["messsage"] = 1024
   # openai_params["n"] = 1
   # openai_params["stop"] = None
   # openai_params["temperature"] = 0.5
    logging.info(json.dumps(openai_params["messages"]))

    job = context.job_queue.run_repeating(send_still_processing, interval=15, first=0, context={"chat_id": update.message.chat_id})

    try:
        openai_response = openai.ChatCompletion.create(**openai_params)
    except Exception as e:
        job.schedule_removal()
        if "InvalidRequestError" in str(e):
            if "maximum context length is" in str(e):
                logging.info(f"Maimum tokens reached. Truncating context and retrying...")
                update.message.reply_text(f"Мой контекст переполнился. Я удалю из него историю старых сообщений и попробую снова...")
                max_tokens = int(str(e).split("maximum context length is ")[1].split(" tokens")[0]) - sum(len(token) for token in training_prompts) - 800
                #max_tokens = openai_params["max_tokens"] - sum(len(token) for token in training_prompts)
                conversation_history_truncated = []
                logging.info(f"HST: {history}")
                for message in reversed(history):
                    if sum(len(token) for token in conversation_history_truncated) < max_tokens:
                        conversation_history_truncated.append(message)
                    else:
                        break
                logging.info(f"HSTT: {conversation_history_truncated}")
                openai_params["messages"] = training_prompts + conversation_history_truncated
                openai_response = openai.ChatCompletion.create(**openai_params)
                history = conversation_history_truncated
        else:
            update.message.reply_text(f"Возникли проблемы, попробуйте повторить запрос позже.")
    # except openai.error.InvalidRequestError as e:
    #     # If the error is due to maximum content length, truncate the conversation history and retry the request

    #     else:
    #        job.schedule_removal()
    #        raise e
    
    response = openai_response.choices[0].message.content.strip()
   
    
    elapsed_time = time.perf_counter() - start_time
    job.schedule_removal()

    tokens_used = openai_response.get("usage", {}).get("total_tokens", 0)
    
    logging.info(f"Response: User: {user_name}, Chat: {chat_name}, Time consumed: {elapsed_time:.2f} seconds, Tokens consumed: {tokens_used}, Message: {response}")

    # Add AI response to the conversation history
    #history += f"{response}\n"
    history = history + [{"role": "assistant", "content": response}]

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

dispatcher.add_handler(MessageHandler((Filters.text & ~Filters.command) & unauthorized_chat_ids_filter, unauthorized_chat))
dispatcher.add_handler(MessageHandler((Filters.text & ~Filters.command) & AllowedChatIDFilter() & (BotNameFilter(bot_names) | IsReplyFilter()), chat_with_gpt))
dispatcher.add_handler(MessageHandler(Filters.all, log_incoming_message))

# Start the Bot
updater.start_polling()
updater.idle()
