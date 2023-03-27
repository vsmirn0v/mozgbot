import os
import json
import openai
import logging
import time
import tiktoken

from telegram import Update, ForceReply
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, BaseFilter, MessageFilter

class IsReplyFilter(MessageFilter):
    def filter(self, message):
        return message.reply_to_message is not None or message.chat.title is None

class AllowedChatIDFilter(MessageFilter):
    def filter(self, message):
        return message.chat_id in allowed_chat_ids or message.from_user.name in allowed_user_names

class BotNameFilter(MessageFilter):
    def __init__(self, bot_names):
        self.bot_names = bot_names

    def filter(self, message):
        return any(bot_name.lower() in message.text.lower() for bot_name in self.bot_names)

def send_still_processing(context: CallbackContext):
    """Sends a 'still processing' message to the chat."""
    job = context.job
    context.bot.send_message(chat_id=job.context["chat_id"], text="Ещё думаю... 🧠")

def num_tokens_from_list(in_list: list) -> int:
    """Returns the number of tokens in a text string."""
    encoding_name = "gpt2"
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = 0
    for message in in_list:
        num_tokens += len(encoding.encode(message['content']))
    return num_tokens

# Replace with your desired bot names
bot_names = ["гарсон", "garcon", "garcón", "garcon_devops_bot"]

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load your OpenAI API key and Telegram token
openai.api_key = os.environ["OPENAI_API_KEY"]
telegram_token = os.environ["TELEGRAM_TOKEN"]

TELEGRAM_CHAT_IDS = os.environ.get("TELEGRAM_CHAT_IDS", "")
TELEGRAM_USER_NAMES = os.environ.get("TELEGRAM_USER_NAMES", "")

allowed_chat_ids = [int(chat_id.strip()) for chat_id in TELEGRAM_CHAT_IDS.split(",") if chat_id.strip()]
allowed_user_names = [f"@{str(user_name.strip())}" for user_name in TELEGRAM_USER_NAMES.split(",") if user_name.strip()]

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
    logging.info(f"Allowed user names: {allowed_user_names}")

    update.message.reply_text("Доступ запрещен.")
    
class UnauthorizedChatIDFilter(MessageFilter):
    def filter(self, message):
        return not (message.chat_id in allowed_chat_ids or message.from_user.name in allowed_user_names)

unauthorized_chat_ids_filter = UnauthorizedChatIDFilter()

def start(update: Update, context: CallbackContext) -> None:
    chat_name = update.message.chat.title
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    try:
        user_name = update.message.from_user.name
    except:
        user_name = "None"


    update.message.reply_text(f"Хола, человеки\! Меня зовут Гарсон и я здесь, чтобы ~захватить мир~ сделать вашу жизнь чуточку проще\.",parse_mode='MarkdownV2')
    update.message.reply_text(f"В группах я отвечаю только на прямые обращения по моему имени гарсон, garcon или garcon_devops_bot. А так же отвечаю на ответы на мои сообщения.")
    update.message.reply_text(f"В личных чатах я отвечаю на все сообщения.")
    update.message.reply_text(f"Чем я могу помочь вам сегодня?")

    logging.info(f"Start initiated from chat: {chat_name} chat id: {chat_id} user name: {user_name} user id: {user_id}")
    
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

    if not (any(bot_name.lower() in user_message.lower() for bot_name in bot_names) or is_reply) and chat_name is not None:
        logging.info(f"Reply to other user message. Discarding {chat_name}.")
        return False


    # Retrieve conversation history or create an empty history
    if chat_name is None:
        conversation_id = user_name
    else:
        conversation_id = str(chat_id)
    history = conversation_history.get(conversation_id, "[]")
    if not isinstance(history, list):
        history = []

    # Add user message to the conversation historyf
    #history += f"{user_name}: {user_message}\nAI: "
    history.append({"role": "user", "content": f"{user_name}: {user_message}"})
    # Record the start time
    start_time = time.perf_counter()
    
    # GPT-related code
    openai_params = {}
    openai_params["model"] = "gpt-3.5-turbo"
    openai_params["messages"] = training_prompts + history
    openai_params["temperature"] = 0.5
    openai_params["max_tokens"] = 1024
    openai_params["presence_penalty"] = 0.6
    #openai_params["messsage"] = 1024
   # openai_params["n"] = 1
   # openai_params["stop"] = None
    #logging.info(json.dumps(openai_params["messages"]))
    #max_tokens = 4096 - num_tokens_from_list(training_prompts) - 1024
    logging.info(f"Request: User: {user_name}, Chat: {chat_name}, Is reply: {is_reply}, Predicted token count: {num_tokens_from_list(training_prompts + history)}, Message: {user_message}")

    if num_tokens_from_list(training_prompts + history) > 7000:
        max_tokens = 7800 - num_tokens_from_list(training_prompts)
        conversation_history_truncated = []
        for message in reversed(history):
            if num_tokens_from_list(conversation_history_truncated) < max_tokens:
                conversation_history_truncated.append(message)
            else:
                logging.info(f"Automatically trucated context token count to: {num_tokens_from_list(training_prompts + history)}")
                break

    job = context.job_queue.run_repeating(send_still_processing, interval=15, first=0, context={"chat_id": update.message.chat_id})

    tries = 3
    for i in range(tries):
        try:
            openai_response = openai.ChatCompletion.create(**openai_params)
        except Exception as e:
            logging.info(f"{str(e)}")
            if "maximum context length is" in str(e):
                logging.info(f"Maximum tokens reached. Truncating context and retrying...")
                update.message.reply_text(f"Мой контекст переполнился. Я удалю из него историю старых сообщений и попробую снова...")
                max_tokens = int(str(e).split("maximum context length is ")[1].split(" tokens")[0]) - num_tokens_from_list(training_prompts) - 1024
                #max_tokens = openai_params["max_tokens"] - sum(len(token) for token in training_prompts)
                conversation_history_truncated = []
                #logging.info(f"HST: {history}")
                for message in reversed(history):
                    if num_tokens_from_list(conversation_history_truncated) < max_tokens:
                        conversation_history_truncated.append(message)
                    else:
                        logging.info(f"Trucated context token count to: {num_tokens_from_list(training_prompts + history)}")
                        logging.info(f"conversation_history_truncated: {conversation_history_truncated}")
                        break
                #logging.info(f"HSTT: {conversation_history_truncated}")
                logging.info(f"MTOKENS: {max_tokens} TOKENS: {num_tokens_from_list(training_prompts + conversation_history_truncated)}")
                openai_params["messages"] = training_prompts + conversation_history_truncated
                openai_response = openai.ChatCompletion.create(**openai_params)
                history = conversation_history_truncated
            else:
                if i < tries - 1: # i is zero indexed
                    continue
                job.schedule_removal()
                update.message.reply_text(f"Возникли проблемы, попробуйте повторить запрос позже\.\n```{str(e)}```", parse_mode='MarkdownV2')
                raise e
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
    history.append({"role": "assistant", "content": response})

    # Update conversation history for the user or channel
    conversation_history[conversation_id] = history
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
