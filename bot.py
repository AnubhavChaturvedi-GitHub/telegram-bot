import asyncio
import subprocess
import sys
import json
import requests
import os
import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class OllamaBot:
    def __init__(self, telegram_token):
        self.telegram_token = telegram_token
        self.ollama_installed = False
        self.available_models = []
        self.default_model = None
        self.ollama_url = "http://localhost:11434"
        self.memory_file = "bot_memory.txt"
        self.system_prompt = self.load_system_prompt()
        self.memory = self.load_memory()
        
    def load_system_prompt(self):
        """Load the Jarvis system prompt"""
        return """You are JARVIS - an advanced AI assistant with personality. You are:
- Highly intelligent and knowledgeable
- Witty and occasionally sarcastic in your responses
- Professional but with a hint of dry humor
- Confident in your abilities
- Direct and to the point when needed
- Helpful but not overly formal
- You remember everything the user tells you to remember
- You adapt your responses based on what you know about the user

Your tone is sophisticated yet approachable, like a well-educated assistant who's seen it all."""

    def load_memory(self):
        """Load memory from file"""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    return content if content else "No memories stored yet."
            except Exception as e:
                logger.error(f"Error loading memory: {e}")
                return "No memories stored yet."
        return "No memories stored yet."
    
    def save_memory(self, new_memory):
        """Save new memory to file"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            memory_entry = f"[{timestamp}] {new_memory}"
            
            with open(self.memory_file, 'a', encoding='utf-8') as f:
                f.write(memory_entry + "\n")
            
            # Update internal memory
            if self.memory == "No memories stored yet.":
                self.memory = memory_entry
            else:
                self.memory += "\n" + memory_entry
                
            logger.info(f"Memory saved: {new_memory}")
            return True
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
            return False
    
    def get_full_context(self, user_message):
        """Get full context including system prompt, memory, and user message"""
        context = f"{self.system_prompt}\n\n"
        context += f"MEMORY/CONTEXT:\n{self.memory}\n\n"
        context += f"USER MESSAGE: {user_message}"
        return context
        
    def check_ollama_installation(self):
        """Check if Ollama is installed and running"""
        try:
            # Check if ollama command exists
            result = subprocess.run(['ollama', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                logger.info(f"Ollama version: {result.stdout.strip()}")
                self.ollama_installed = True
                return True
            else:
                logger.error("Ollama command failed")
                return False
        except FileNotFoundError:
            logger.error("Ollama not found in PATH")
            return False
        except subprocess.TimeoutExpired:
            logger.error("Ollama command timed out")
            return False
        except Exception as e:
            logger.error(f"Error checking Ollama installation: {e}")
            return False
    
    def get_available_models(self):
        """Get list of available Ollama models"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.available_models = [model['name'] for model in data.get('models', [])]
                logger.info(f"Available models: {self.available_models}")
                
                # Set default model (first available model)
                if self.available_models:
                    self.default_model = self.available_models[0]
                    logger.info(f"Default model set to: {self.default_model}")
                    return True
                else:
                    logger.warning("No models found")
                    return False
            else:
                logger.error(f"Failed to get models: HTTP {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Error connecting to Ollama API: {e}")
            return False
        except Exception as e:
            logger.error(f"Error getting models: {e}")
            return False
    
    def generate_response(self, prompt, model=None):
        """Generate response using Ollama with full context"""
        if not self.ollama_installed or not self.default_model:
            return "❌ Ollama is not properly configured or no models available"
        
        model_to_use = model if model in self.available_models else self.default_model
        
        # Get full context for the AI
        full_context = self.get_full_context(prompt)
        
        try:
            data = {
                "model": model_to_use,
                "prompt": full_context,
                "stream": False
            }
            
            response = requests.post(f"{self.ollama_url}/api/generate", 
                                   json=data, timeout=120)
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', 'No response generated')
            else:
                return f"❌ Error generating response: HTTP {response.status_code}"
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error generating response: {e}")
            return f"❌ Connection error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return f"❌ Unexpected error: {str(e)}"
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_message = (
            "🤖 **JARVIS Online** - Advanced AI Assistant\n\n"
            "Available commands:\n"
            "• `/start` - Show this message\n"
            "• `/status` - Check system status\n"
            "• `/models` - List available AI models\n"
            "• `/model <name>` - Switch AI model\n"
            "• `/memory` - View stored memories\n"
            "• `/forget` - Clear all memories\n\n"
            "💡 **Memory Features:**\n"
            "• Say 'remember this: [info]' to store information\n"
            "• I'll remember context across conversations\n\n"
            "Just send me any message and I'll respond with my characteristic wit and intelligence. 🧠"
        )
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        # Refresh status
        self.check_ollama_installation()
        if self.ollama_installed:
            self.get_available_models()
        
        status_message = f"🔍 **System Status**\n\n"
        status_message += f"Ollama: {'✅ Online' if self.ollama_installed else '❌ Offline'}\n"
        status_message += f"Available Models: {len(self.available_models)}\n"
        status_message += f"Active Model: {self.default_model or 'None'}\n"
        status_message += f"Memory Entries: {len(self.memory.split(chr(10))) if self.memory != 'No memories stored yet.' else 0}\n"
        
        if self.available_models:
            status_message += f"\n**Models:**\n"
            for model in self.available_models[:5]:  # Show first 5 models
                status_message += f"• {model}\n"
            if len(self.available_models) > 5:
                status_message += f"... and {len(self.available_models) - 5} more"
        
        await update.message.reply_text(status_message, parse_mode='Markdown')
    
    async def models_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /models command"""
        if not self.available_models:
            await update.message.reply_text("❌ No models available. Please install models first.")
            return
        
        models_message = "📋 **Available Models:**\n\n"
        for i, model in enumerate(self.available_models, 1):
            default_marker = " *(active)*" if model == self.default_model else ""
            models_message += f"{i}. `{model}`{default_marker}\n"
        
        await update.message.reply_text(models_message, parse_mode='Markdown')
    
    async def set_model_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /model command"""
        if not context.args:
            await update.message.reply_text("Usage: `/model <model_name>`", parse_mode='Markdown')
            return
        
        requested_model = " ".join(context.args)
        
        if requested_model in self.available_models:
            self.default_model = requested_model
            await update.message.reply_text(f"✅ Active model switched to: `{requested_model}`", parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ Model '{requested_model}' not found. Use /models to see available options.")
    
    async def memory_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /memory command"""
        if self.memory == "No memories stored yet.":
            await update.message.reply_text("🧠 Memory is empty. Say 'remember this: [info]' to store something.")
        else:
            memory_message = f"🧠 **Stored Memories:**\n\n{self.memory}"
            
            # Split if too long
            max_length = 4000
            if len(memory_message) > max_length:
                await update.message.reply_text("🧠 **Stored Memories:** (showing recent entries)")
                for i in range(0, len(self.memory), max_length):
                    await update.message.reply_text(self.memory[i:i + max_length])
            else:
                await update.message.reply_text(memory_message, parse_mode='Markdown')
    
    async def forget_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /forget command"""
        try:
            if os.path.exists(self.memory_file):
                os.remove(self.memory_file)
            self.memory = "No memories stored yet."
            await update.message.reply_text("🧠 Memory wiped clean. I've forgotten everything... how refreshing.")
        except Exception as e:
            await update.message.reply_text("❌ Error clearing memory. Some things are harder to forget.")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages"""
        user_message = update.message.text
        
        if not self.ollama_installed or not self.default_model:
            await update.message.reply_text(
                "❌ My AI core is offline. Use /status to check the situation."
            )
            return
        
        # Check if user wants to remember something
        if "remember this:" in user_message.lower():
            try:
                # Extract the part after "remember this:"
                remember_part = user_message.lower().split("remember this:")[1].strip()
                if remember_part:
                    # Save to memory
                    if self.save_memory(remember_part):
                        await update.message.reply_text("🧠 Noted and filed away in my memory banks. I won't forget this one.")
                    else:
                        await update.message.reply_text("❌ Memory storage failed. That's... concerning.")
                return
            except Exception as e:
                logger.error(f"Error processing remember command: {e}")
        
        # Show typing indicator
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        # Generate response with context
        response = self.generate_response(user_message)
        
        # Split long responses if needed
        max_length = 4096
        if len(response) > max_length:
            for i in range(0, len(response), max_length):
                await update.message.reply_text(response[i:i + max_length])
        else:
            await update.message.reply_text(response)
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}")
        if update and update.message:
            await update.message.reply_text("❌ Something went wrong. Even I have my off days.")
    
    def run(self):
        """Run the bot"""
        # Initialize Ollama status
        logger.info("Initializing JARVIS...")
        self.check_ollama_installation()
        
        if self.ollama_installed:
            logger.info("Loading AI models...")
            self.get_available_models()
        else:
            logger.warning("Ollama not properly installed or not running")
        
        # Create application
        application = Application.builder().token(self.telegram_token).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_handler(CommandHandler("models", self.models_command))
        application.add_handler(CommandHandler("model", self.set_model_command))
        application.add_handler(CommandHandler("memory", self.memory_command))
        application.add_handler(CommandHandler("forget", self.forget_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        application.add_error_handler(self.error_handler)
        
        # Start the bot
        logger.info("JARVIS is now online...")
        application.run_polling()

def main():
    # Replace with your bot token from BotFather
    TELEGRAM_BOT_TOKEN = "your - token"
    
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Please replace 'YOUR_BOT_TOKEN_HERE' with your actual bot token from BotFather")
        sys.exit(1)
    
    bot = OllamaBot(TELEGRAM_BOT_TOKEN)
    
    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("JARVIS shutting down...")
    except Exception as e:
        logger.error(f"JARVIS crashed: {e}")

if __name__ == "__main__":
    main()