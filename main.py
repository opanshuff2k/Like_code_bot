import asyncio
import re
import logging
import os
import json
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button, types, errors
from telethon.errors import (
    SessionPasswordNeededError, 
    PhoneCodeInvalidError,
    ApiIdInvalidError,
    PhoneNumberInvalidError,
    MessageNotModifiedError
)
from telethon.tl.types import (
    MessageEntityCode, 
    MessageEntityPre, 
    MessageEntityTextUrl,
    ReplyInlineMarkup
)
from telethon.tl.functions.messages import GetHistoryRequest, CheckChatInviteRequest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Your credentials
API_ID = 34613950
API_HASH = "94def5c9badbf7394718b07a72f84379"
BOT_TOKEN = "8675773925:AAGWf2CFIVfV5nmQXm1pQMsPQ3wzEtdIIEk"

# Owner IDs
OWNER_IDS = [1134292389, 6038965890, 6667476799, 7580298442]

# QR Code Image Path
QR_IMAGE_PATH = "/storage/emulated/0/Pictures/Telegram/IMG_20260626_081844_128.jpg"

# Premium Plans
PREMIUM_PLANS = {
    "1day": {"name": "1 Days Unlimited", "price": 59, "days": 1},
    "1week": {"name": "1 Week Unlimited", "price": 199, "days": 7},
    "1month": {"name": "1 Month Unlimited", "price": 299, "days": 30},
    "3month": {"name": "3 Month Unlimited", "price": 399, "days": 90},
}

# Files for data storage
USER_DATA_FILE = "user_sessions.json"
USER_BALANCE_FILE = "user_balances.json"
ID_STORAGE_FILE = "stored_ids.json"
TOTAL_USERS_FILE = "total_users.json"
CODE_HISTORY_FILE = "code_history.json"
TOTAL_DEPOSITS_FILE = "total_deposits.json"
PROCESSED_DEPOSITS_FILE = "processed_deposits.json"
SUPPORT_REPLY_FILE = "support_replies.json"
PREMIUM_USERS_FILE = "premium_users.json"
PENDING_DEPOSITS_FILE = "pending_deposits.json"

# Global storage
USER_SESSIONS = {}
USER_DATA = {}
USER_BALANCES = {}
STORED_IDS = {}
TOTAL_USERS = set()
CODE_HISTORY = {}
TOTAL_DEPOSITS = {}
PROCESSED_DEPOSITS = set()
SUPPORT_REPLIES = {}
PREMIUM_USERS = {}
PENDING_DEPOSITS_STORAGE = {}

# Price per code
PRICE_PER_CODE = 10

BOT_SESSION_NAME = "bot_session_v6"

class AdvancedLikeBot:
    def __init__(self):
        self.bot = None
        self.user_states = {}
        self.pending_deposits = {}
        self.load_all_data()
        
    def load_all_data(self):
        global USER_DATA, USER_BALANCES, STORED_IDS, TOTAL_USERS, CODE_HISTORY, TOTAL_DEPOSITS, PROCESSED_DEPOSITS, SUPPORT_REPLIES, PREMIUM_USERS, PENDING_DEPOSITS_STORAGE
        
        # Delete old bot sessions
        for old_file in os.listdir('.'):
            if old_file.startswith('bot_session') and old_file.endswith(('.session', '.session-journal')):
                if old_file != f"{BOT_SESSION_NAME}.session" and old_file != f"{BOT_SESSION_NAME}.session-journal":
                    try:
                        os.remove(old_file)
                        logger.info(f"🗑️ Deleted old session: {old_file}")
                    except:
                        pass
        
        data_files = {
            USER_DATA_FILE: (USER_DATA, dict),
            USER_BALANCE_FILE: (USER_BALANCES, dict),
            ID_STORAGE_FILE: (STORED_IDS, dict),
            TOTAL_USERS_FILE: (TOTAL_USERS, set),
            CODE_HISTORY_FILE: (CODE_HISTORY, dict),
            TOTAL_DEPOSITS_FILE: (TOTAL_DEPOSITS, dict),
            PROCESSED_DEPOSITS_FILE: (PROCESSED_DEPOSITS, set),
            SUPPORT_REPLY_FILE: (SUPPORT_REPLIES, dict),
            PREMIUM_USERS_FILE: (PREMIUM_USERS, dict),
            PENDING_DEPOSITS_FILE: (PENDING_DEPOSITS_STORAGE, dict),
        }
        
        for file_path, (storage, default_type) in data_files.items():
            try:
                if os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                        if default_type == set:
                            storage.update(set(data))
                        elif default_type == dict:
                            storage.update(data)
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")
        
        # Restore pending deposits from storage
        for deposit_id, deposit_data in PENDING_DEPOSITS_STORAGE.items():
            self.pending_deposits[deposit_id] = deposit_data
    
    def save_all_data(self):
        data_to_save = {
            USER_DATA_FILE: USER_DATA,
            USER_BALANCE_FILE: USER_BALANCES,
            ID_STORAGE_FILE: STORED_IDS,
            TOTAL_USERS_FILE: list(TOTAL_USERS),
            CODE_HISTORY_FILE: CODE_HISTORY,
            TOTAL_DEPOSITS_FILE: TOTAL_DEPOSITS,
            PROCESSED_DEPOSITS_FILE: list(PROCESSED_DEPOSITS),
            SUPPORT_REPLY_FILE: SUPPORT_REPLIES,
            PREMIUM_USERS_FILE: PREMIUM_USERS,
        }
        for file_path, data in data_to_save.items():
            try:
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Error saving {file_path}: {e}")
        
        # Save pending deposits separately
        try:
            with open(PENDING_DEPOSITS_FILE, 'w') as f:
                json.dump(self.pending_deposits, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving pending deposits: {e}")
    
    def is_owner(self, user_id):
        return user_id in OWNER_IDS
    
    def get_user_balance(self, user_id):
        return float(USER_BALANCES.get(str(user_id), 0))
    
    def get_total_deposits(self, user_id):
        return float(TOTAL_DEPOSITS.get(str(user_id), 0))
    
    def add_user_balance(self, user_id, amount):
        user_id_str = str(user_id)
        current = self.get_user_balance(user_id)
        USER_BALANCES[user_id_str] = current + float(amount)
        total_dep = self.get_total_deposits(user_id)
        TOTAL_DEPOSITS[user_id_str] = total_dep + float(amount)
        self.save_all_data()
    
    def deduct_user_balance(self, user_id, amount):
        user_id_str = str(user_id)
        current = self.get_user_balance(user_id)
        USER_BALANCES[user_id_str] = current - float(amount)
        self.save_all_data()
    
    def get_user_codes_count(self, user_id):
        if str(user_id) in CODE_HISTORY:
            return len(CODE_HISTORY[str(user_id)])
        return 0
    
    def is_premium(self, user_id):
        user_id_str = str(user_id)
        if user_id_str in PREMIUM_USERS:
            expiry = datetime.fromisoformat(PREMIUM_USERS[user_id_str]['expiry'])
            if datetime.now() < expiry:
                return True
            else:
                try:
                    asyncio.create_task(self._send_premium_expired_notification(int(user_id)))
                except:
                    pass
                del PREMIUM_USERS[user_id_str]
                self.save_all_data()
        return False
    
    async def _send_premium_expired_notification(self, user_id):
        try:
            await asyncio.sleep(1)
            user = await self.bot.get_entity(user_id)
            user_name = user.first_name or "Unknown"
            user_username = user.username or "Unknown"
            balance = self.get_user_balance(user_id)
            
            notify_msg = f"""🐲 Premium Expired 🐲

👤 Name: {user_name}
📛 Username: @{user_username}
🆔 User ID: {user_id}
💰 Coins: ₹{balance:.2f}
🐲 Status: Premium Not Active ❌"""
            
            await self.notify_all_owners(notify_msg)
            
            try:
                await self.bot.send_message(
                    user_id,
                    "🐲 Your Premium Has Expired ❌\n\nYour premium plan has ended.\nGet premium again for unlimited codes! ∞",
                    parse_mode='markdown'
                )
            except:
                pass
        except Exception as e:
            logger.error(f"Error sending premium expiry: {e}")
    
    def add_premium(self, user_id, days):
        expiry = (datetime.now() + timedelta(days=int(days))).isoformat()
        plan_name = f"{days} Days"
        
        plan_key = f"custom_{days}d"
        for key, plan in PREMIUM_PLANS.items():
            if plan['days'] == int(days):
                plan_key = key
                plan_name = plan['name']
                break
        
        PREMIUM_USERS[str(user_id)] = {
            'plan': plan_key,
            'plan_name': plan_name,
            'expiry': expiry,
            'days': int(days),
            'activated_at': datetime.now().isoformat()
        }
        self.save_all_data()
    
    def remove_premium(self, user_id):
        user_id_str = str(user_id)
        if user_id_str in PREMIUM_USERS:
            del PREMIUM_USERS[user_id_str]
            self.save_all_data()
            return True
        return False
    
    def get_premium_expiry(self, user_id):
        user_id_str = str(user_id)
        if user_id_str in PREMIUM_USERS:
            return datetime.fromisoformat(PREMIUM_USERS[user_id_str]['expiry'])
        return None
    
    def get_premium_time_left(self, user_id):
        expiry = self.get_premium_expiry(user_id)
        if expiry:
            remaining = expiry - datetime.now()
            if remaining.total_seconds() <= 0:
                return "Expired"
            
            days = remaining.days
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if days > 0:
                return f"{days}d {hours}h {minutes}m"
            elif hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            else:
                return f"{minutes}m {seconds}s"
        return "N/A"
    
    def get_premium_days_left(self, user_id):
        expiry = self.get_premium_expiry(user_id)
        if expiry:
            remaining = (expiry - datetime.now()).days
            return max(0, remaining)
        return 0
    
    def get_balance_display(self, user_id):
        balance = self.get_user_balance(user_id)
        if self.is_premium(user_id):
            if balance > 0:
                return f"₹{balance:.2f} / ∞"
            else:
                return "∞"
        else:
            return f"₹{balance:.2f}"
    
    async def notify_all_owners(self, message, parse_mode='markdown'):
        """Send notification to ALL owners"""
        for owner_id in OWNER_IDS:
            try:
                await self.bot.send_message(owner_id, message, parse_mode=parse_mode)
            except Exception as e:
                logger.error(f"Failed to notify owner {owner_id}: {e}")
    
    async def notify_owners_except(self, message, exclude_id, parse_mode='markdown'):
        """Send notification to all owners except the one who did the action"""
        for owner_id in OWNER_IDS:
            if owner_id != exclude_id:
                try:
                    await self.bot.send_message(owner_id, message, parse_mode=parse_mode)
                except Exception as e:
                    logger.error(f"Failed to notify owner {owner_id}: {e}")
    
    async def notify_premium_added(self, target_user_id, days, added_by_name):
        """Notify owners about new premium user"""
        try:
            user = await self.bot.get_entity(target_user_id)
            user_name = user.first_name or "Unknown"
            user_username = user.username or "Unknown"
            balance = self.get_user_balance(target_user_id)
            
            notify_msg = f"""🐲 New Premium User Added 🐲

👤 Name: {user_name}
📛 Username: @{user_username}
🆔 User ID: {target_user_id}
💰 Coins: ₹{balance:.2f}
⏰ Duration: {days} Days
🐲 Status: Premium Active ✅
👑 Added By: {added_by_name}"""
            
            await self.notify_all_owners(notify_msg)
            
            try:
                await self.bot.send_message(
                    target_user_id,
                    f"🐲 Premium Activated!\n\n⏰ Duration: {days} Days\n📅 Expires in: {days} days\n\nEnjoy unlimited code fetching! ∞",
                    parse_mode='markdown'
                )
            except:
                pass
        except Exception as e:
            logger.error(f"Error notifying premium: {e}")
    
    async def safe_edit(self, event, text, buttons=None, parse_mode='markdown'):
        try:
            await event.edit(text, buttons=buttons, parse_mode=parse_mode)
        except MessageNotModifiedError:
            pass
        except Exception as e:
            logger.error(f"Edit error: {e}")
    
    async def extract_channel_and_message(self, client, post_link):
        try:
            post_link = post_link.strip()
            if '?' in post_link:
                post_link = post_link.split('?')[0]
            
            match = re.search(r'/c/(\d+)/(\d+)', post_link)
            if match:
                channel_id = int(match.group(1))
                message_id = int(match.group(2))
                for fmt in [int(f"-100{channel_id}"), int(f"-{channel_id}"), types.PeerChannel(channel_id)]:
                    try:
                        channel = await client.get_entity(fmt)
                        message = await client.get_messages(channel, ids=message_id)
                        if message:
                            return channel, message
                    except:
                        continue
            
            match = re.search(r't\.me/([^/\s]+)/(\d+)', post_link)
            if match and match.group(1) not in ['c', 'joinchat', 'boost']:
                try:
                    channel = await client.get_entity(match.group(1))
                    message = await client.get_messages(channel, ids=int(match.group(2)))
                    if message:
                        return channel, message
                except:
                    pass
            
            try:
                message = await client.get_messages(post_link)
                if message:
                    chat = await client.get_entity(message.peer_id)
                    return chat, message
            except:
                pass
            
            return None, None
        except Exception as e:
            logger.error(f"Extract error: {e}")
            return None, None
    
    async def restore_sessions(self):
        for user_id_str, data in USER_DATA.items():
            try:
                user_id = int(user_id_str)
                session_file = f"user_{user_id}.session"
                if os.path.exists(session_file):
                    client = TelegramClient(
                        session_file, API_ID, API_HASH,
                        device_model='Samsung Galaxy S23',
                        system_version='Android 13',
                        app_version='10.3.2',
                        lang_code='en', system_lang_code='en-US',
                    )
                    await client.connect()
                    if await client.is_user_authorized():
                        USER_SESSIONS[user_id] = client
                        logger.info(f"✅ Restored session for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to restore session for {user_id_str}: {e}")
        logger.info(f"🔄 Restored {len(USER_SESSIONS)} active sessions")
    
    async def forward_to_owners(self, message, from_user_id):
        try:
            user = await self.bot.get_entity(from_user_id)
            first_name = user.first_name or "Unknown"
            username = user.username or "Unknown"
        except:
            first_name = "Unknown"; username = "Unknown"
        
        user_info = f"""🆘 New Support Message

👤 Name: {first_name}
📛 Username: @{username}
🆔 User ID: {from_user_id}

📝 Message:"""
        
        for owner_id in OWNER_IDS:
            try:
                await self.bot.send_message(owner_id, user_info, parse_mode='markdown')
                await self.bot.forward_messages(owner_id, message, from_user_id)
            except Exception as e:
                logger.error(f"Failed to forward to owner {owner_id}: {e}")
    
    async def start(self):
        try:
            self.bot = TelegramClient(
                BOT_SESSION_NAME, API_ID, API_HASH,
                device_model='Desktop', system_version='Windows 10',
                app_version='4.0', lang_code='en', system_lang_code='en-US',
            )
            await self.bot.start(bot_token=BOT_TOKEN)
            await self.restore_sessions()
            me = await self.bot.get_me()
            logger.info(f"✅ Bot started as @{me.username}")
            self.register_handlers()
            
            print(f"""
{'='*60}
🤖 ADVANCED @LIKE CODE FETCHER BOT v6.0
{'='*60}
📡 Bot: @{me.username}
👑 Owners: {len(OWNER_IDS)}
📊 Sessions: {len(USER_SESSIONS)} | Users: {len(TOTAL_USERS)}
💰 Price: ₹{PRICE_PER_CODE}/code | 🐲 Premium: ENABLED
🌍 OTP: Mobile Device | 📱 QR: In-Message
💾 Pending Deposits: {len(self.pending_deposits)}
{'='*60}
            """)
            
            await self.bot.run_until_disconnected()
        except Exception as e:
            logger.error(f"❌ Failed to start bot: {e}")
    
    def register_handlers(self):
        
        @self.bot.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            user_id = event.sender_id
            
            if user_id not in TOTAL_USERS:
                TOTAL_USERS.add(user_id)
                self.save_all_data()
                try:
                    user = await self.bot.get_entity(user_id)
                    await self.notify_all_owners(f"""➕ New User Notification ➕

👤 User: {user.first_name} {f'(@{user.username})' if user.username else ''}
🔥 User ID: {user_id}
😁 Total Users: {len(TOTAL_USERS)}""")
                except:
                    pass
            
            try:
                user = await self.bot.get_entity(user_id)
                first_name = user.first_name or "User"
            except:
                first_name = "User"
            
            premium_status = ""
            if self.is_premium(user_id):
                time_left = self.get_premium_time_left(user_id)
                premium_status = f"\n🐲 Premium: Active ({time_left})"
            
            keyboard = [
                [Button.inline("💰 Balance", b"menu_balance"), Button.inline("💳 Deposit", b"menu_deposit")],
                [Button.inline("🔑 Get Code", b"menu_getcode"), Button.inline("🆘 Support", b"menu_support")],
                [Button.inline("🐲 GET PREMIUM", b"menu_premium")],
                [Button.inline("🔐 Login", b"menu_login"), Button.inline("🚪 Logout", b"menu_logout")]
            ]
            
            if self.is_owner(user_id):
                keyboard.append([Button.inline("👑 Admin Panel", b"menu_admin")])
            
            await event.reply(f"""🤖 Welcome to Advanced @like Code Fetcher Bot!

👋 Hello {first_name}!{premium_status}

✨ Features:
• Extract hidden @like codes from posts
• Works with private & public channels
• International phone support (All Countries)
• Secure deposit system with QR
• 🐲 Premium plans available

💰 Price: ₹{PRICE_PER_CODE} per code | 🐲 Premium: FREE ∞

💡 Select an option below:""", buttons=keyboard, parse_mode='markdown')
        
        @self.bot.on(events.CallbackQuery())
        async def callback_handler(event):
            user_id = event.sender_id
            data = event.data.decode('utf-8')
            
            # Ignore already processed buttons
            if data.startswith("approved_") or data.startswith("rejected_") or data.startswith("done_"):
                await event.answer("⚠️ This deposit is already processed!", alert=True)
                return
            
            # Menu handlers
            if data == "menu_balance": await self.show_balance(event, user_id)
            elif data == "menu_deposit": await self.show_deposit(event, user_id)
            elif data == "menu_getcode": await self.show_getcode(event, user_id)
            elif data == "menu_support": await self.show_support(event, user_id)
            elif data == "menu_premium": await self.show_premium_plans(event, user_id)
            elif data == "menu_login": await self.show_login(event, user_id)
            elif data == "menu_logout": await self.handle_logout(event, user_id)
            elif data == "menu_admin": await self.show_admin_panel(event, user_id)
            elif data == "deposit_pay": await self.show_payment_amount(event, user_id)
            elif data == "back_to_main": await self.back_to_main(event, user_id)
            elif data == "login_start": await self.start_login_process(event, user_id)
            elif data == "fetch_code": await self.fetch_code_start(event, user_id)
            elif data == "go_to_deposit": await self.show_deposit(event, user_id)
            elif data.startswith("premium_"): await self.show_premium_payment(event, user_id, data.replace("premium_", ""))
            elif data.startswith("approve_"): await self.approve_deposit(event, data.replace("approve_", ""), user_id)
            elif data.startswith("reject_"): await self.reject_deposit(event, data.replace("reject_", ""), user_id)
            elif data == "admin_add_balance": await self.admin_add_balance_start(event, user_id)
            elif data == "admin_cut_balance": await self.admin_cut_balance_start(event, user_id)
            elif data == "admin_add_premium": await self.admin_add_premium_start(event, user_id)
            elif data == "admin_remove_premium": await self.admin_remove_premium_start(event, user_id)
            elif data == "admin_view_ids": await self.admin_view_all_ids(event, user_id)
            elif data == "admin_view_users": await self.admin_view_users(event, user_id)
            elif data == "admin_user_info": await self.admin_user_info_start(event, user_id)
            elif data == "admin_code_history": await self.admin_code_history(event, user_id)
            elif data == "admin_broadcast": await self.admin_broadcast_start(event, user_id)
            
            await event.answer()
        
        @self.bot.on(events.NewMessage())
        async def message_handler(event):
            user_id = event.sender_id
            
            if self.is_owner(user_id) and event.is_reply:
                replied_msg = await event.get_reply_message()
                if replied_msg and replied_msg.forward:
                    await self.handle_owner_support_reply(event, user_id, replied_msg)
                    return
            
            if user_id not in self.user_states:
                return
            
            if event.text and event.text.startswith('/'):
                return
            
            state = self.user_states[user_id].get('state')
            
            state_handlers = {
                'awaiting_phone': self.handle_phone,
                'awaiting_otp': self.handle_otp,
                'awaiting_password': self.handle_password,
                'awaiting_id_name': self.handle_id_name,
                'awaiting_post_link': self.handle_post_link,
                'awaiting_deposit_amount': self.handle_deposit_amount,
                'awaiting_deposit_screenshot': self.handle_deposit_screenshot,
                'awaiting_premium_screenshot': self.handle_premium_screenshot,
                'awaiting_support_message': self.handle_support_message,
                'awaiting_broadcast': self.handle_broadcast,
                'awaiting_admin_add_balance_user': self.handle_admin_add_balance_user,
                'awaiting_admin_add_balance_amount': self.handle_admin_add_balance_amount,
                'awaiting_admin_cut_balance_user': self.handle_admin_cut_balance_user,
                'awaiting_admin_cut_balance_amount': self.handle_admin_cut_balance_amount,
                'awaiting_admin_add_premium_user': self.handle_admin_add_premium_user,
                'awaiting_admin_add_premium_days': self.handle_admin_add_premium_days,
                'awaiting_admin_remove_premium_user': self.handle_admin_remove_premium_user,
                'awaiting_admin_user_info': self.handle_admin_user_info,
            }
            
            if state in state_handlers:
                await state_handlers[state](event, user_id)
    
    async def handle_owner_support_reply(self, event, owner_id, replied_msg):
        try:
            original_sender = None
            
            if hasattr(replied_msg, 'forward') and replied_msg.forward:
                forward = replied_msg.forward
                
                if hasattr(forward, 'from_id') and forward.from_id:
                    if hasattr(forward.from_id, 'user_id'):
                        original_sender = forward.from_id.user_id
                    elif isinstance(forward.from_id, int):
                        original_sender = forward.from_id
                
                if not original_sender and hasattr(forward, 'sender_id') and forward.sender_id:
                    if hasattr(forward.sender_id, 'user_id'):
                        original_sender = forward.sender_id.user_id
                    elif isinstance(forward.sender_id, int):
                        original_sender = forward.sender_id
                
                if not original_sender:
                    try:
                        fd = forward.to_dict()
                        if 'from_id' in fd and fd['from_id']:
                            fid = fd['from_id']
                            if isinstance(fid, dict) and 'user_id' in fid:
                                original_sender = fid['user_id']
                            elif isinstance(fid, int):
                                original_sender = fid
                    except:
                        pass
            
            if not original_sender:
                await event.reply("❌ Could not identify sender.")
                return
            
            reply_text = event.message.text if event.message.text else ""
            
            if reply_text:
                await self.bot.send_message(original_sender, f"📬 Reply from Support:\n\n{reply_text}", parse_mode='markdown')
            elif event.message.media:
                await self.bot.send_file(original_sender, event.message.media, caption=f"📬 Reply from Support:\n\n{event.message.text or ''}", parse_mode='markdown')
            
            await event.reply("✅ Reply sent to user anonymously.")
        except Exception as e:
            await event.reply(f"❌ Error: {e}")
    
    # ============ MAIN MENU ============
    
    async def back_to_main(self, event, user_id):
        try:
            user = await self.bot.get_entity(user_id)
            first_name = user.first_name or "User"
        except:
            first_name = "User"
        
        premium_status = ""
        if self.is_premium(user_id):
            time_left = self.get_premium_time_left(user_id)
            premium_status = f"\n🐲 Premium: {time_left}"
        
        keyboard = [
            [Button.inline("💰 Balance", b"menu_balance"), Button.inline("💳 Deposit", b"menu_deposit")],
            [Button.inline("🔑 Get Code", b"menu_getcode"), Button.inline("🆘 Support", b"menu_support")],
            [Button.inline("🐲 GET PREMIUM", b"menu_premium")],
            [Button.inline("🔐 Login", b"menu_login"), Button.inline("🚪 Logout", b"menu_logout")]
        ]
        
        if self.is_owner(user_id):
            keyboard.append([Button.inline("👑 Admin Panel", b"menu_admin")])
        
        await self.safe_edit(event, f"🤖 Main Menu\n\n👋 Hello {first_name}!{premium_status}\n💰 Price: ₹{PRICE_PER_CODE}/code | 🐲 FREE", buttons=keyboard)
    
    async def handle_logout(self, event, user_id):
        if user_id in USER_SESSIONS:
            try: await USER_SESSIONS[user_id].disconnect()
            except: pass
            del USER_SESSIONS[user_id]
            try: os.remove(f"user_{user_id}.session")
            except: pass
        if str(user_id) in USER_DATA:
            del USER_DATA[str(user_id)]
            self.save_all_data()
        if user_id in self.user_states:
            del self.user_states[user_id]
        await self.safe_edit(event, "🚪 Logged Out Successfully!\n\n✅ All sessions cleared.", buttons=[[Button.inline("🔙 Back", b"back_to_main")]])
    
    async def show_balance(self, event, user_id):
        try:
            user = await self.bot.get_entity(user_id)
            first_name = user.first_name or "User"
        except:
            first_name = "User"
        
        is_prem = self.is_premium(user_id)
        balance_display = self.get_balance_display(user_id)
        
        if is_prem:
            time_left = self.get_premium_time_left(user_id)
            expiry = self.get_premium_expiry(user_id)
            expiry_str = expiry.strftime('%Y-%m-%d %H:%M:%S') if expiry else "N/A"
            premium_status = f"🐲 Premium: Active ✅\n⏰ Time Left: {time_left}\n📅 Expires: {expiry_str}"
        else:
            premium_status = "🐲 Premium: Not Active ❌"
        
        await self.safe_edit(event,
            f"🌟 User: {first_name}\n➖➖➖➖➖➖➖➖➖➖➖\n💸 Your Balance: {balance_display}\n{premium_status}\n💥 User ID: {user_id}",
            buttons=[[Button.inline("🔙 Back", b"back_to_main")]])
    
    async def show_deposit(self, event, user_id):
        deposit_text = """<blockquote>🔥 Pay To Get Paid Access.

💰 UPI: nazmulrand@fam ✅</blockquote>"""
        
        keyboard = [
            [Button.inline("💳 PAID ✅", b"deposit_pay")],
            [Button.inline("🔙 Back", b"back_to_main")]
        ]
        
        if os.path.exists(QR_IMAGE_PATH):
            try:
                await self.bot.send_file(event.chat_id, QR_IMAGE_PATH, caption=deposit_text, buttons=keyboard, parse_mode='html')
                await event.delete()
            except:
                await self.safe_edit(event, deposit_text, buttons=keyboard, parse_mode='html')
        else:
            await self.safe_edit(event, deposit_text, buttons=keyboard, parse_mode='html')
    
    async def show_payment_amount(self, event, user_id):
        self.user_states[user_id] = {'state': 'awaiting_deposit_amount'}
        await self.safe_edit(event, "💰 Enter Amount How Much You Want To Pay...", buttons=[[Button.inline("🔙 Back", b"menu_deposit")]])
    
    # ============ PREMIUM SYSTEM ============
    
    async def show_premium_plans(self, event, user_id):
        if self.is_premium(user_id):
            time_left = self.get_premium_time_left(user_id)
            await self.safe_edit(event,
                f"🐲 Premium Active!\n\n⏰ Time Remaining: {time_left}\n\nEnjoy unlimited code fetching! ∞",
                buttons=[[Button.inline("🔙 Back", b"back_to_main")]])
            return
        
        premium_text = f"""🐲 GET PREMIUM 🐲

Unlock unlimited code fetching!

📋 Choose Your Plan:

🐲 1 Days Unlimited - ₹59
🐲 1 Week Unlimited - ₹199
🐲 1 Month Unlimited - ₹299
🐲 3 Month Unlimited - ₹399

💡 Premium benefits:
• Unlimited code fetching ∞
• No per-code charges
• Priority support"""
        
        keyboard = [
            [Button.inline("🐲 1 Day - ₹59", b"premium_1day")],
            [Button.inline("🐲 1 Week - ₹199", b"premium_1week")],
            [Button.inline("🐲 1 Month - ₹299", b"premium_1month")],
            [Button.inline("🐲 3 Month - ₹399", b"premium_3month")],
            [Button.inline("🔙 Back", b"back_to_main")]
        ]
        
        await self.safe_edit(event, premium_text, buttons=keyboard)
    
    async def show_premium_payment(self, event, user_id, plan_key):
        plan = PREMIUM_PLANS[plan_key]
        
        payment_text = f"""<blockquote>🔥 Pay To Get Paid Access.

💰 UPI: nazmulrand@fam ✅

🐲 Plan: {plan['name']}
💸 Amount: ₹{plan['price']}</blockquote>"""
        
        self.user_states[user_id] = {
            'state': 'awaiting_premium_screenshot',
            'premium_plan': plan_key,
            'premium_price': plan['price']
        }
        
        keyboard = [[Button.inline("🔙 Back", b"menu_premium")]]
        
        if os.path.exists(QR_IMAGE_PATH):
            try:
                await self.bot.send_file(event.chat_id, QR_IMAGE_PATH, caption=payment_text, buttons=keyboard, parse_mode='html')
                await event.delete()
            except:
                await self.safe_edit(event, payment_text, buttons=keyboard, parse_mode='html')
        else:
            await self.safe_edit(event, payment_text, buttons=keyboard, parse_mode='html')
        
        await self.bot.send_message(
            event.chat_id,
            f"📸 Please send payment screenshot\n\n🐲 Plan: {plan['name']}\n💰 Amount: ₹{plan['price']}\n📱 UPI: nazmulrand@fam",
            parse_mode='markdown'
        )
    
    async def handle_premium_screenshot(self, event, user_id):
        if not event.message.media:
            await event.reply("❌ Send screenshot!"); return
        
        plan_key = self.user_states[user_id].get('premium_plan', '1day')
        price = self.user_states[user_id].get('premium_price', 59)
        plan = PREMIUM_PLANS[plan_key]
        
        try:
            user = await self.bot.get_entity(user_id)
            username, first_name = user.username, user.first_name
        except:
            username, first_name = "Unknown", "Unknown"
        
        deposit_id = f"prem_{user_id}_{int(datetime.now().timestamp())}"
        self.pending_deposits[deposit_id] = {
            'user_id': user_id, 'amount': price, 'username': username,
            'first_name': first_name, 'timestamp': datetime.now().isoformat(),
            'premium_plan': plan_key, 'is_premium': True
        }
        self.save_all_data()
        
        owner_msg = f"""🐲 New Premium Purchase Request

👤 User: {first_name} {f'(@{username})' if username else ''}
🆔 User ID: {user_id}
🐲 Plan: {plan['name']}
💸 Amount: ₹{price}
📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Payment Screenshot: ⬇️"""
        
        keyboard = [[Button.inline("✅ Approve", f"approve_{deposit_id}"), Button.inline("❌ Reject", f"reject_{deposit_id}")]]
        
        for owner_id in OWNER_IDS:
            try:
                await self.bot.send_file(owner_id, event.message.media, caption=owner_msg, buttons=keyboard, parse_mode='markdown')
            except: pass
        
        await event.reply("✅ Payment screenshot sent!\n\nPlease wait for admin approval.\nYou will be notified once approved.", parse_mode='markdown')
        if user_id in self.user_states: del self.user_states[user_id]
    
    async def show_getcode(self, event, user_id):
        balance = self.get_user_balance(user_id)
        is_prem = self.is_premium(user_id)
        balance_display = self.get_balance_display(user_id)
        
        if not is_prem and balance < PRICE_PER_CODE:
            await self.safe_edit(event,
                f"❌ Insufficient Balance!\n\n💸 Your Balance: ₹{balance:.2f}\n💰 Required: ₹{PRICE_PER_CODE}\n\n🐲 Or get PREMIUM for ∞ access!",
                buttons=[
                    [Button.inline("💳 Go to Add Fund", b"go_to_deposit")],
                    [Button.inline("🐲 GET PREMIUM", b"menu_premium")],
                    [Button.inline("🔙 Back", b"back_to_main")]
                ])
            return
        
        if is_prem:
            time_left = self.get_premium_time_left(user_id)
            ids_text = f"🐲 Premium Active! ({time_left})\n\n💸 Balance: {balance_display}\n💵 Price: FREE ∞\n\nSend post link to extract code."
        elif str(user_id) in STORED_IDS and STORED_IDS[str(user_id)]:
            ids_text = f"📋 Your Stored IDs:\n\n"
            for id_name in STORED_IDS[str(user_id)]:
                ids_text += f"• {id_name}\n"
            ids_text += f"\n💸 Balance: ₹{balance:.2f}\n💵 Price: ₹{PRICE_PER_CODE}/code\n\nClick below:"
        else:
            ids_text = f"📝 Get @like Code\n\n💸 Balance: ₹{balance:.2f}\n💵 Price: ₹{PRICE_PER_CODE}/code\n\nSend post link to extract code."
        
        await self.safe_edit(event, ids_text,
            buttons=[[Button.inline("🔍 Fetch Code", b"fetch_code")], [Button.inline("🔐 Login New ID", b"login_start")], [Button.inline("🔙 Back", b"back_to_main")]])
    
    async def show_support(self, event, user_id):
        self.user_states[user_id] = {'state': 'awaiting_support_message'}
        await self.safe_edit(event, "🆘 Support\n\nSend your message to owner:\n\nPlease describe your issue in detail.", buttons=[[Button.inline("🔙 Back", b"back_to_main")]])
    
    async def handle_support_message(self, event, user_id):
        await self.forward_to_owners(event.message, user_id)
        await event.reply("✅ Your message has been sent to the owner!\n\nYou will receive a reply soon.", buttons=[[Button.inline("🔙 Back", b"back_to_main")]], parse_mode='markdown')
        if user_id in self.user_states: del self.user_states[user_id]
    
    async def show_login(self, event, user_id):
        await self.safe_edit(event,
            "🔐 Login to Your Account\n\n🌍 Supports ALL countries!\n🇮🇳 India | 🇩🇪 Germany | 🇺🇸 USA | 🇬🇧 UK\n\nClick below to start:",
            buttons=[[Button.inline("🔐 Start Login", b"login_start")], [Button.inline("🔙 Back", b"back_to_main")]])
    
    async def show_admin_panel(self, event, user_id):
        if not self.is_owner(user_id):
            await event.answer("❌ Access Denied!", alert=True); return
        
        total_ids = sum(len(ids) for ids in STORED_IDS.values())
        total_codes = sum(len(codes) for codes in CODE_HISTORY.values())
        total_premium = len(PREMIUM_USERS)
        
        await self.safe_edit(event,
            f"👑 Admin Panel\n\n📊 Statistics:\n• Total Users: {len(TOTAL_USERS)}\n• Stored IDs: {total_ids}\n• Codes Fetched: {total_codes}\n• Premium Users: {total_premium}\n\nSelect an option:",
            buttons=[
                [Button.inline("💰 Add Balance", b"admin_add_balance"), Button.inline("💸 Cut Balance", b"admin_cut_balance")],
                [Button.inline("🐲 Add Premium", b"admin_add_premium"), Button.inline("❌ Remove Premium", b"admin_remove_premium")],
                [Button.inline("📋 View All IDs", b"admin_view_ids"), Button.inline("👥 View Users", b"admin_view_users")],
                [Button.inline("🔍 User Info", b"admin_user_info"), Button.inline("📊 Code History", b"admin_code_history")],
                [Button.inline("📢 Broadcast", b"admin_broadcast")],
                [Button.inline("🔙 Back", b"back_to_main")]
            ])
    
    # ============ ADMIN PREMIUM HANDLERS ============
    
    async def admin_add_premium_start(self, event, user_id):
        if not self.is_owner(user_id): return
        self.user_states[user_id] = {'state': 'awaiting_admin_add_premium_user'}
        await self.safe_edit(event, "🐲 Add Premium User 🐲\n\nSend Username or User ID:", buttons=[[Button.inline("🔙 Back", b"menu_admin")]])
    
    async def handle_admin_add_premium_user(self, event, user_id):
        target = event.message.text.strip().replace('@', '')
        try:
            try:
                target_user = await self.bot.get_entity(int(target))
            except:
                target_user = await self.bot.get_entity(target)
            
            current_balance = self.get_user_balance(target_user.id)
            is_prem = self.is_premium(target_user.id)
            prem_info = ""
            if is_prem:
                time_left = self.get_premium_time_left(target_user.id)
                prem_info = f"\n🐲 Current Premium: Active ({time_left})"
            
            self.user_states[user_id] = {
                'state': 'awaiting_admin_add_premium_days',
                'target_user_id': target_user.id,
                'target_name': target_user.first_name or 'Unknown',
                'target_username': target_user.username or 'Unknown',
                'current_balance': current_balance
            }
            
            await event.reply(
                f"👤 Target: {target_user.first_name} (@{target_user.username or 'N/A'})\n"
                f"🆔 ID: {target_user.id}\n"
                f"💵 Balance: ₹{current_balance:.2f}{prem_info}\n\n"
                f"⌛ Enter the premium duration (in days):",
                parse_mode='markdown')
        except:
            await event.reply("❌ User not found.")
    
    async def handle_admin_add_premium_days(self, event, user_id):
        try:
            days = int(event.message.text.strip())
            if days <= 0:
                await event.reply("❌ Enter valid days (1 or more).")
                return
            
            target_user_id = self.user_states[user_id]['target_user_id']
            target_name = self.user_states[user_id]['target_name']
            
            self.add_premium(target_user_id, days)
            
            try:
                approver = await self.bot.get_entity(user_id)
                approver_name = f"@{approver.username}" if approver.username else approver.first_name
            except:
                approver_name = "Admin"
            
            await event.reply(
                f"✅ Premium Added Successfully! 🐲\n\n"
                f"👤 User: {target_name}\n"
                f"⏰ Duration: {days} Days\n"
                f"🐲 Status: Premium Active ✅",
                parse_mode='markdown')
            
            await self.notify_premium_added(target_user_id, days, approver_name)
            
        except ValueError:
            await event.reply("❌ Please enter a valid number.")
        
        if user_id in self.user_states: del self.user_states[user_id]
    
    async def admin_remove_premium_start(self, event, user_id):
        if not self.is_owner(user_id): return
        self.user_states[user_id] = {'state': 'awaiting_admin_remove_premium_user'}
        await self.safe_edit(event, "❌ Remove Premium User\n\nSend Username or User ID:", buttons=[[Button.inline("🔙 Back", b"menu_admin")]])
    
    async def handle_admin_remove_premium_user(self, event, user_id):
        target = event.message.text.strip().replace('@', '')
        try:
            try:
                target_user = await self.bot.get_entity(int(target))
            except:
                target_user = await self.bot.get_entity(target)
            
            if not self.is_premium(target_user.id):
                await event.reply("❌ This user doesn't have premium!")
                if user_id in self.user_states: del self.user_states[user_id]
                return
            
            self.remove_premium(target_user.id)
            
            target_name = target_user.first_name or "Unknown"
            
            await event.reply(
                f"✅ Premium Removed Successfully! ❌\n\n"
                f"👤 User: {target_name}\n"
                f"🐲 Status: Premium Not Active ❌",
                parse_mode='markdown')
            
            await self.notify_all_owners(f"🐲 Premium Removed\n\n👤 User: {target_name}\n🆔 User ID: {target_user.id}\n🐲 Status: Premium Not Active ❌")
            
            try:
                await self.bot.send_message(
                    target_user.id,
                    "🐲 Your Premium Has Been Removed by Admin ❌\n\nContact support if you have questions.",
                    parse_mode='markdown'
                )
            except: pass
            
        except:
            await event.reply("❌ User not found.")
        
        if user_id in self.user_states: del self.user_states[user_id]
    
    # ============ LOGIN HANDLERS ============
    
    async def start_login_process(self, event, user_id):
        self.user_states[user_id] = {'state': 'awaiting_phone'}
        await self.safe_edit(event, "📲 Please send your phone number in international format\n\nExamples:\n🇮🇳 India: +919876543210\n🇩🇪 Germany: +491234567890\n🇺🇸 USA: +11234567890\n🇬🇧 UK: +441234567890\n\n⚠️ Include country code (+XX)")
    
    async def handle_phone(self, event, user_id):
        phone = event.message.text.strip()
        if not phone.startswith('+'):
            await event.reply("❌ Please include country code!\n\nExamples:\n🇩🇪 +491234567890 (Germany)\n🇮🇳 +919876543210 (India)\n🇺🇸 +11234567890 (USA)"); return
        phone = '+' + re.sub(r'[^\d]', '', phone[1:])
        if len(phone) < 8:
            await event.reply("❌ Invalid phone number length!"); return
        
        try:
            processing_msg = await event.reply("⌛ Sending OTP... Please wait.\n🌍 International delivery may take a moment.")
            client = TelegramClient(f"user_{user_id}", API_ID, API_HASH,
                device_model='Samsung Galaxy S23', system_version='Android 13',
                app_version='10.3.2', lang_code='en', system_lang_code='en-US',
                connection_retries=3, retry_delay=1, timeout=30)
            await client.connect()
            
            try:
                result = await client.send_code_request(phone=phone, force_sms=True)
            except:
                result = await client.send_code_request(phone=phone, force_sms=False)
            
            self.user_states[user_id] = {
                'state': 'awaiting_otp', 'client': client,
                'phone': phone, 'phone_code_hash': result.phone_code_hash,
                'session_name': f"user_{user_id}"
            }
            await processing_msg.edit("📨 OTP sent!\n\nPlease send in this format:\n`1 2 3 4 5` (space by space)\n\n📱 Check your Telegram app/SMS\n🌍 International numbers may take 1-2 minutes.", parse_mode='markdown')
        except Exception as e:
            await event.reply(f"❌ Error: {e}")
            if user_id in self.user_states: del self.user_states[user_id]
    
    async def handle_otp(self, event, user_id):
        code = event.message.text.strip().replace(' ', '')
        if not code.isdigit():
            await event.reply("❌ Invalid code format!\nSend as: 1 2 3 4 5"); return
        
        user_data = self.user_states[user_id]
        try:
            await user_data['client'].sign_in(phone=user_data['phone'], code=code, phone_code_hash=user_data['phone_code_hash'])
            me = await user_data['client'].get_me()
            USER_SESSIONS[user_id] = user_data['client']
            USER_DATA[str(user_id)] = {'phone': user_data['phone'], 'session_name': user_data['session_name'], 'saved_at': datetime.now().isoformat()}
            self.save_all_data()
            
            self.user_states[user_id] = {
                'state': 'awaiting_id_name', 'client': user_data['client'],
                'id_details': {'name': me.first_name or 'Unknown', 'username': me.username or 'Unknown', 'user_id': me.id, 'phone': user_data['phone']}
            }
            await event.reply(f"✅ Login Successful!\n\n📱 Account: {me.first_name}\n🔑 User ID: {me.id}\n🌍 Phone: {user_data['phone']}\n\n📝 Please enter a name for this ID:\n(Example: My Germany Account)", parse_mode='markdown')
        except SessionPasswordNeededError:
            self.user_states[user_id]['state'] = 'awaiting_password'
            await event.reply("🔐 2-Step Verification Enabled!\n\nPlease send your 2FA password.")
        except Exception as e:
            await event.reply(f"❌ Login failed: {e}")
            if user_id in self.user_states: del self.user_states[user_id]
    
    async def handle_password(self, event, user_id):
        try:
            await self.user_states[user_id]['client'].sign_in(password=event.message.text.strip())
            me = await self.user_states[user_id]['client'].get_me()
            USER_SESSIONS[user_id] = self.user_states[user_id]['client']
            USER_DATA[str(user_id)] = {'phone': self.user_states[user_id].get('phone', 'Unknown'), 'session_name': self.user_states[user_id].get('session_name', ''), 'saved_at': datetime.now().isoformat()}
            self.save_all_data()
            
            self.user_states[user_id] = {
                'state': 'awaiting_id_name', 'client': self.user_states[user_id]['client'],
                'id_details': {'name': me.first_name or 'Unknown', 'username': me.username or 'Unknown', 'user_id': me.id, 'phone': self.user_states[user_id].get('phone', 'Unknown')}
            }
            await event.reply(f"✅ Login Successful!\n\n📱 Account: {me.first_name}\n🔑 User ID: {me.id}\n\n📝 Please enter a name for this ID:", parse_mode='markdown')
        except Exception as e:
            await event.reply(f"❌ Wrong password: {e}")
            if user_id in self.user_states: del self.user_states[user_id]
    
    async def handle_id_name(self, event, user_id):
        id_name = event.message.text.strip()
        id_details = self.user_states[user_id]['id_details']
        if str(user_id) not in STORED_IDS: STORED_IDS[str(user_id)] = {}
        STORED_IDS[str(user_id)][id_name] = id_details
        self.save_all_data()
        
        try:
            adder = await self.bot.get_entity(user_id)
            await self.notify_all_owners(f"😁 THIS USER ADDED A ID : {adder.first_name} (@{adder.username})\n\nID DETAILS:\nName: {id_details['name']}\nUsername: @{id_details['username']}\nUser ID: {id_details['user_id']}\nPhone No.: {id_details['phone']}")
        except: pass
        
        self.user_states[user_id] = {'state': 'logged_in'}
        await event.reply(f"✅ ID Saved Successfully!\n\n📛 Name: {id_name}\n👤 Account: {id_details['name']}\n📱 Phone: {id_details['phone']}\n\nNow you can fetch codes!", buttons=[[Button.inline("🔙 Back to Menu", b"back_to_main")]], parse_mode='markdown')
    
    # ============ FETCH CODE ============
    
    async def fetch_code_start(self, event, user_id):
        is_prem = self.is_premium(user_id)
        if not is_prem and self.get_user_balance(user_id) < PRICE_PER_CODE:
            await event.answer(f"❌ Need ₹{PRICE_PER_CODE} or PREMIUM!", alert=True); return
        if user_id not in USER_SESSIONS:
            await event.answer("❌ Login first!", alert=True); return
        
        self.user_states[user_id] = {'state': 'awaiting_post_link'}
        await self.safe_edit(event, "📝 Send Post Link\n\nWorks with both private & public channels!\n\nExamples:\n• `https://t.me/c/4470385969/2`\n• `https://t.me/channel/123`\n\nSend /cancel to cancel", buttons=[[Button.inline("🔙 Back", b"menu_getcode")]])
    
    async def handle_post_link(self, event, user_id):
        if event.text == '/cancel':
            if user_id in self.user_states: del self.user_states[user_id]
            await event.reply("❌ Cancelled."); return
        
        post_link = event.message.text.strip()
        is_prem = self.is_premium(user_id)
        if not is_prem and self.get_user_balance(user_id) < PRICE_PER_CODE:
            await event.reply(f"❌ Need ₹{PRICE_PER_CODE} or PREMIUM!"); return
        
        await self.extract_and_charge(event, user_id, post_link)
    
    async def extract_and_charge(self, event, user_id, post_link):
        client = USER_SESSIONS.get(user_id)
        if not client:
            await event.reply("❌ Login first!"); return
        
        try:
            processing_msg = await event.reply("🔍 Deep scanning for @like code...")
            channel, message = await self.extract_channel_and_message(client, post_link)
            
            if not channel or not message:
                await processing_msg.edit("❌ Cannot access this post!\n\nMake sure:\n• The account is a member of the channel\n• The post link is correct"); return
            
            channel_name = channel.title if hasattr(channel, 'title') else "Unknown"
            all_codes = self.deep_extract_codes(message)
            
            if all_codes:
                like_code = all_codes[0]
                is_prem = self.is_premium(user_id)
                
                if not is_prem:
                    self.deduct_user_balance(user_id, PRICE_PER_CODE)
                
                balance_display = self.get_balance_display(user_id)
                
                try:
                    user = await self.bot.get_entity(user_id)
                    user_name = user.first_name or "Unknown"
                    user_username = user.username or "Unknown"
                except:
                    user_name, user_username = "Unknown", "Unknown"
                
                if str(user_id) not in CODE_HISTORY:
                    CODE_HISTORY[str(user_id)] = []
                
                CODE_HISTORY[str(user_id)].append({
                    'code': like_code, 'channel': channel_name,
                    'channel_id': str(channel.id), 'post_link': post_link,
                    'timestamp': datetime.now().isoformat(), 'price': 0 if is_prem else PRICE_PER_CODE
                })
                self.save_all_data()
                
                if is_prem:
                    price_text = "FREE (🐲 PREMIUM USER)"
                else:
                    price_text = f"₹{PRICE_PER_CODE}"
                
                await processing_msg.edit(
                    f"✅ @like ID Found!\n\n📌 Code: #{like_code}\n\n📢 Channel: {channel_name}\n🆔 Channel ID: {str(channel.id).replace('-100', '')}\n\n💰 Deducted: {price_text}\n💸 Balance: {balance_display}",
                    parse_mode='markdown')
                
                # DETAILED owner notification
                owner_notify = f"""🔑 Code Fetched!

👤 Name: {user_name}
📛 Username: @{user_username}
🆔 User ID: {user_id}

📢 Channel: {channel_name}
🔗 Post: {post_link}
📌 Code: #{like_code}

💰 Deducted: {price_text}"""
                
                await self.notify_all_owners(owner_notify)
            else:
                full_text = (message.text or message.message or "")[:300]
                await processing_msg.edit(f"❌ No @like code found in this post.\n\n📢 Channel: {channel_name}\n\nMessage Preview:\n```\n{full_text}\n```\n\n💡 Make sure this is a @like bot post.", parse_mode='markdown')
        except Exception as e:
            await event.reply(f"❌ Error: {e}")
        
        if user_id in self.user_states: del self.user_states[user_id]
    
    def deep_extract_codes(self, message):
        codes = []
        full_text = (message.text or message.message or "") + " " + str(message)
        
        if full_text.strip():
            for pattern in [
                r'#([a-f0-9]{12,20})', r'#([a-f0-9]{8,32})', r'([a-f0-9]{12,20})',
                r'(dc[a-f0-9]{10,18})', r'@like.*?#([a-f0-9]+)', r'@like[^\n]*?([a-f0-9]{8,32})',
                r'like.*?#([a-f0-9]+)', r'code[:\s]*#?([a-f0-9]{8,32})'
            ]:
                codes.extend(re.findall(pattern, full_text, re.IGNORECASE))
        
        if message.entities:
            for entity in message.entities:
                if isinstance(entity, (MessageEntityCode, MessageEntityPre)):
                    try: codes.extend(re.findall(r'([a-f0-9]{8,32})', full_text[entity.offset:entity.offset+entity.length], re.IGNORECASE))
                    except: pass
        
        if hasattr(message, 'buttons') and message.buttons:
            for row in message.buttons:
                for button in row:
                    if hasattr(button, 'text'):
                        codes.extend(re.findall(r'([a-f0-9]{8,32})', str(button.text), re.IGNORECASE))
        
        valid = []
        for code in codes:
            code = code.strip().lower()
            if 8 <= len(code) <= 32 and not code.isdigit() and not code.startswith(('http', 't.me', 'www')) and code not in valid:
                valid.append(code)
        return valid
    
    # ============ DEPOSIT ============
    
    async def handle_deposit_amount(self, event, user_id):
        try:
            amount = float(event.message.text.strip())
            if amount <= 0:
                await event.reply("❌ Please enter a valid amount greater than 0."); return
            
            self.user_states[user_id] = {'state': 'awaiting_deposit_screenshot', 'amount': amount}
            await event.reply(f"🔥 Send Payment Screenshot...\n\nAmount: ₹{amount:.2f}\nUPI: nazmulrand@fam\n\nPlease upload the screenshot of your payment.", parse_mode='markdown')
        except ValueError:
            await event.reply("❌ Please enter a valid number.")
    
    async def handle_deposit_screenshot(self, event, user_id):
        if not event.message.media:
            await event.reply("❌ Please send a screenshot/image of your payment."); return
        
        amount = self.user_states[user_id]['amount']
        try:
            user = await self.bot.get_entity(user_id)
            username, first_name = user.username, user.first_name
        except:
            username, first_name = "Unknown", "Unknown"
        
        deposit_id = f"dep_{user_id}_{int(datetime.now().timestamp())}"
        self.pending_deposits[deposit_id] = {
            'user_id': user_id, 'amount': amount, 'username': username,
            'first_name': first_name, 'timestamp': datetime.now().isoformat()
        }
        self.save_all_data()  # SAVE PENDING DEPOSITS
        
        owner_msg = f"""💰 New Deposit Request

👤 User: {first_name} {f'(@{username})' if username else ''}
🆔 User ID: {user_id}
💸 Amount: ₹{amount:.2f}
📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Payment Screenshot: ⬇️"""
        
        keyboard = [[Button.inline("✅ Approve", f"approve_{deposit_id}"), Button.inline("❌ Reject", f"reject_{deposit_id}")]]
        
        for owner_id in OWNER_IDS:
            try:
                await self.bot.send_file(owner_id, event.message.media, caption=owner_msg, buttons=keyboard, parse_mode='markdown')
            except: pass
        
        await event.reply("✅ Payment screenshot sent!\n\nPlease wait for admin approval.\nYou will be notified once approved.", parse_mode='markdown')
        if user_id in self.user_states: del self.user_states[user_id]
    
    async def approve_deposit(self, event, deposit_id, approver_id):
        if not self.is_owner(approver_id): await event.answer("❌ Only admin can approve!", alert=True); return
        
        # Check if already processed
        if deposit_id in PROCESSED_DEPOSITS:
            await event.answer("⚠️ This deposit is already processed!", alert=True); return
        
        # Check if pending (NOW PERSISTENT)
        if deposit_id not in self.pending_deposits:
            await event.answer("❌ Deposit not found in pending list!", alert=True); return
        
        deposit = self.pending_deposits[deposit_id]
        user_id = deposit['user_id']
        amount = deposit['amount']
        
        try:
            approver = await self.bot.get_entity(approver_id)
            approver_username = approver.username or "Unknown"
        except:
            approver_username = "Unknown"
        
        if deposit.get('is_premium'):
            plan_key = deposit.get('premium_plan', '1day')
            plan = PREMIUM_PLANS[plan_key]
            self.add_premium(user_id, plan['days'])
            PROCESSED_DEPOSITS.add(deposit_id)
            self.save_all_data()
            
            try:
                await self.bot.send_message(user_id,
                    f"✅ Your Deposit Has Been Approved By Admin ☠\n\n🐲 Plan: {plan['name']}\n⏰ Duration: {plan['days']} Days\n\nEnjoy unlimited codes! ∞", parse_mode='markdown')
            except: pass
            
            await self.notify_premium_added(user_id, plan['days'], f"@{approver_username}")
        else:
            self.add_user_balance(user_id, amount)
            new_balance = self.get_user_balance(user_id)
            PROCESSED_DEPOSITS.add(deposit_id)
            self.save_all_data()
            
            try:
                await self.bot.send_message(user_id,
                    f"✅ Your Deposit Has Been Approved By Admin ☠\n\n💰 Amount Added: ₹{amount:.2f}\n💵 Total Amount: ₹{new_balance:.2f}", parse_mode='markdown')
            except: pass
            
            # Notify all owners about balance addition
            try:
                user = await self.bot.get_entity(user_id)
                user_name = user.first_name or "Unknown"
                user_username = user.username or "Unknown"
                
                await self.notify_all_owners(f"""✅ Deposit Approved - Coins Added

👤 Name: {user_name}
📛 Username: @{user_username}
🆔 User ID: {user_id}
💰 Amount Added: ₹{amount:.2f}
💵 New Balance: ₹{new_balance:.2f}
👑 Approved By: @{approver_username}""")
            except: pass
        
        # Update owner's message
        try:
            new_caption = event.message.text.replace("💰 New Deposit Request", f"✅ ACCEPTED BY @{approver_username.upper()} ✅")
            new_caption = new_caption.replace("🐲 New Premium Purchase Request", f"✅ ACCEPTED BY @{approver_username.upper()} ✅")
            await self.bot.edit_message(event.chat_id, event.message.id, new_caption, buttons=None, parse_mode='markdown')
        except: pass
        
        # Remove from pending
        if deposit_id in self.pending_deposits:
            del self.pending_deposits[deposit_id]
        self.save_all_data()
        await event.answer("✅ Deposit Approved Successfully!", alert=True)
    
    async def reject_deposit(self, event, deposit_id, rejecter_id):
        if not self.is_owner(rejecter_id): await event.answer("❌ Only admin can reject!", alert=True); return
        
        if deposit_id in PROCESSED_DEPOSITS:
            await event.answer("⚠️ This deposit is already processed!", alert=True); return
        
        if deposit_id not in self.pending_deposits:
            await event.answer("❌ Deposit not found in pending list!", alert=True); return
        
        deposit = self.pending_deposits[deposit_id]
        user_id = deposit['user_id']
        
        try:
            rejecter = await self.bot.get_entity(rejecter_id)
            rejecter_username = rejecter.username or "Unknown"
        except:
            rejecter_username = "Unknown"
        
        PROCESSED_DEPOSITS.add(deposit_id)
        self.save_all_data()
        
        try:
            await self.bot.send_message(user_id, "❌ Your Deposit Has Been Rejected By Admin 🤡", parse_mode='markdown')
        except: pass
        
        # Update owner's message
        try:
            new_caption = event.message.text.replace("💰 New Deposit Request", f"❌ REJECTED BY @{rejecter_username.upper()} ❌")
            new_caption = new_caption.replace("🐲 New Premium Purchase Request", f"❌ REJECTED BY @{rejecter_username.upper()} ❌")
            await self.bot.edit_message(event.chat_id, event.message.id, new_caption, buttons=None, parse_mode='markdown')
        except: pass
        
        if deposit_id in self.pending_deposits:
            del self.pending_deposits[deposit_id]
        self.save_all_data()
        await event.answer("❌ Deposit Rejected!", alert=True)
    
    # ============ ADMIN ============
    
    async def admin_add_balance_start(self, event, user_id):
        if not self.is_owner(user_id): return
        self.user_states[user_id] = {'state': 'awaiting_admin_add_balance_user'}
        await self.safe_edit(event, "💰 Add Balance\n\nSend Username or User ID:", buttons=[[Button.inline("🔙 Back", b"menu_admin")]])
    
    async def handle_admin_add_balance_user(self, event, user_id):
        target = event.message.text.strip().replace('@', '')
        try:
            try: target_user = await self.bot.get_entity(int(target))
            except: target_user = await self.bot.get_entity(target)
            self.user_states[user_id] = {'state': 'awaiting_admin_add_balance_amount', 'target_user_id': target_user.id, 'target_name': target_user.first_name or 'Unknown', 'target_username': target_user.username or 'Unknown'}
            await event.reply(f"👤 Target: {target_user.first_name} (@{target_user.username or 'N/A'})\n🆔 ID: {target_user.id}\n💵 Current Balance: ₹{self.get_user_balance(target_user.id):.2f}\n\n💰 Enter amount to add:", parse_mode='markdown')
        except: await event.reply("❌ User not found.")
    
    async def handle_admin_add_balance_amount(self, event, user_id):
        try:
            amount = float(event.message.text.strip())
            tid = self.user_states[user_id]['target_user_id']
            target_name = self.user_states[user_id]['target_name']
            target_username = self.user_states[user_id].get('target_username', 'Unknown')
            
            self.add_user_balance(tid, amount)
            nb = self.get_user_balance(tid)
            
            try:
                approver = await self.bot.get_entity(user_id)
                approver_name = f"@{approver.username}" if approver.username else approver.first_name
            except:
                approver_name = "Admin"
            
            await event.reply(f"✅ Balance Added Successfully!\n\n👤 User: {target_name}\n💰 Added: ₹{amount:.2f}\n💵 New Balance: ₹{nb:.2f}", parse_mode='markdown')
            
            # Notify user
            try: await self.bot.send_message(tid, f"✅ Balance Added by Admin!\n\n💰 Amount: ₹{amount:.2f}\n💵 Total Balance: ₹{nb:.2f}", parse_mode='markdown')
            except: pass
            
            # Notify all owners
            await self.notify_all_owners(f"""💰 Balance Added by Admin

👤 Name: {target_name}
📛 Username: @{target_username}
🆔 User ID: {tid}
💰 Amount Added: ₹{amount:.2f}
💵 New Balance: ₹{nb:.2f}
👑 Added By: {approver_name}""")
            
        except ValueError: await event.reply("❌ Please enter a valid amount.")
        if user_id in self.user_states: del self.user_states[user_id]
    
    async def admin_cut_balance_start(self, event, user_id):
        if not self.is_owner(user_id): return
        self.user_states[user_id] = {'state': 'awaiting_admin_cut_balance_user'}
        await self.safe_edit(event, "💸 Cut Balance\n\nSend Username or User ID:", buttons=[[Button.inline("🔙 Back", b"menu_admin")]])
    
    async def handle_admin_cut_balance_user(self, event, user_id):
        target = event.message.text.strip().replace('@', '')
        try:
            try: target_user = await self.bot.get_entity(int(target))
            except: target_user = await self.bot.get_entity(target)
            cb = self.get_user_balance(target_user.id)
            self.user_states[user_id] = {'state': 'awaiting_admin_cut_balance_amount', 'target_user_id': target_user.id, 'target_name': target_user.first_name or 'Unknown', 'target_username': target_user.username or 'Unknown', 'current_balance': cb}
            await event.reply(f"👤 Target: {target_user.first_name} (@{target_user.username or 'N/A'})\n💵 Current Balance: ₹{cb:.2f}\n\n💸 Enter amount to cut:", parse_mode='markdown')
        except: await event.reply("❌ User not found.")
    
    async def handle_admin_cut_balance_amount(self, event, user_id):
        try:
            amount = float(event.message.text.strip())
            tid = self.user_states[user_id]['target_user_id']
            target_name = self.user_states[user_id]['target_name']
            target_username = self.user_states[user_id].get('target_username', 'Unknown')
            
            self.deduct_user_balance(tid, amount)
            nb = self.get_user_balance(tid)
            
            try:
                approver = await self.bot.get_entity(user_id)
                approver_name = f"@{approver.username}" if approver.username else approver.first_name
            except:
                approver_name = "Admin"
            
            await event.reply(f"✅ Balance Cut Successfully!\n\n👤 User: {target_name}\n💸 Cut: ₹{amount:.2f}\n💵 New Balance: ₹{nb:.2f}", parse_mode='markdown')
            
            try: await self.bot.send_message(tid, f"⚠️ Balance Deducted by Admin\n\n💸 Amount: ₹{amount:.2f}\n💵 Remaining Balance: ₹{nb:.2f}", parse_mode='markdown')
            except: pass
            
            # Notify all owners
            await self.notify_all_owners(f"""💸 Balance Cut by Admin

👤 Name: {target_name}
📛 Username: @{target_username}
🆔 User ID: {tid}
💸 Amount Cut: ₹{amount:.2f}
💵 New Balance: ₹{nb:.2f}
👑 Cut By: {approver_name}""")
            
        except ValueError: await event.reply("❌ Please enter a valid amount.")
        if user_id in self.user_states: del self.user_states[user_id]
    
    async def admin_user_info_start(self, event, user_id):
        if not self.is_owner(user_id): return
        self.user_states[user_id] = {'state': 'awaiting_admin_user_info'}
        await self.safe_edit(event, "🔍 User Info\n\nSend Username or User ID to get details:", buttons=[[Button.inline("🔙 Back", b"menu_admin")]])
    
    async def handle_admin_user_info(self, event, user_id):
        target = event.message.text.strip().replace('@', '')
        try:
            try: target_user = await self.bot.get_entity(int(target))
            except: target_user = await self.bot.get_entity(target)
            
            balance = self.get_user_balance(target_user.id)
            total_dep = self.get_total_deposits(target_user.id)
            codes = self.get_user_codes_count(target_user.id)
            is_prem = self.is_premium(target_user.id)
            
            if is_prem:
                time_left = self.get_premium_time_left(target_user.id)
                prem_status = f"🐲 Premium: Active ✅ ({time_left})"
            else:
                prem_status = "🐲 Premium: Not Active ❌"
            
            await event.reply(
                f"🔍 User Info\n\n"
                f"👤 Name: {target_user.first_name or 'Unknown'}\n"
                f"📛 Username: @{target_user.username or 'Unknown'}\n"
                f"🆔 User ID: {target_user.id}\n\n"
                f"📊 Stats:\n"
                f"🔑 Codes Fetched: {codes}\n"
                f"💰 Balance: ₹{balance:.2f}\n"
                f"💵 Total Deposited: ₹{total_dep:.2f}\n"
                f"{prem_status}",
                buttons=[[Button.inline("🔙 Back", b"menu_admin")]], parse_mode='markdown')
        except: await event.reply("❌ User not found.")
        if user_id in self.user_states: del self.user_states[user_id]
    
    async def admin_view_all_ids(self, event, user_id):
        if not self.is_owner(user_id): return
        if not STORED_IDS: await self.safe_edit(event, "❌ No IDs stored yet.", buttons=[[Button.inline("🔙 Back", b"menu_admin")]]); return
        text = "📋 All Stored IDs:\n\n"
        for uid, ids in STORED_IDS.items():
            try: adder = (await self.bot.get_entity(int(uid))).first_name or "Unknown"
            except: adder = "Unknown"
            text += f"**{adder}** (`{uid}`) ADDED:\n"
            for n, d in ids.items(): text += f"  • {n}\n    Name: {d.get('name')}\n    Username: @{d.get('username')}\n    User ID: {d.get('user_id')}\n    Phone: {d.get('phone')}\n\n"
        await self.safe_edit(event, text, buttons=[[Button.inline("🔙 Back", b"menu_admin")]])
    
    async def admin_view_users(self, event, user_id):
        if not self.is_owner(user_id): return
        text = f"👥 Total Users: {len(TOTAL_USERS)}\n\n"
        for i, uid in enumerate(list(TOTAL_USERS)[:20], 1):
            try:
                u = await self.bot.get_entity(int(uid))
                pm = "🐲" if self.is_premium(uid) else ""
                text += f"{i}. {pm} {u.first_name or 'Unknown'} (@{u.username or 'N/A'})\n   ID: {uid} | Balance: ₹{self.get_user_balance(uid):.2f}\n\n"
            except: text += f"{i}. Unknown (`{uid}`)\n\n"
        if len(TOTAL_USERS) > 20: text += f"\n...and {len(TOTAL_USERS) - 20} more users"
        await self.safe_edit(event, text, buttons=[[Button.inline("🔙 Back", b"menu_admin")]])
    
    async def admin_code_history(self, event, user_id):
        if not self.is_owner(user_id): return
        if not CODE_HISTORY: await self.safe_edit(event, "❌ No codes fetched yet.", buttons=[[Button.inline("🔙 Back", b"menu_admin")]]); return
        text = "📊 Code Fetch History:\n\n"; total = 0
        for uid, codes in CODE_HISTORY.items():
            try: n = (await self.bot.get_entity(int(uid))).first_name or "Unknown"
            except: n = "Unknown"
            text += f"**{n}** (`{uid}`): {len(codes)} codes\n"
            for c in codes[-3:]: text += f"  • #{c['code']} - {c['channel']}\n"
            text += "\n"; total += len(codes)
        text += f"📊 Total Codes Fetched: {total}\n💰 Total Revenue: ₹{total * PRICE_PER_CODE}"
        await self.safe_edit(event, text, buttons=[[Button.inline("🔙 Back", b"menu_admin")]])
    
    async def admin_broadcast_start(self, event, user_id):
        if not self.is_owner(user_id): return
        self.user_states[user_id] = {'state': 'awaiting_broadcast'}
        await self.safe_edit(event, "📢 Broadcast Mode\n\nSend the message to broadcast to all users.\nSend /cancel to cancel.", buttons=[[Button.inline("🔙 Cancel", b"menu_admin")]])
    
    async def handle_broadcast(self, event, user_id):
        if event.text == '/cancel':
            if user_id in self.user_states: del self.user_states[user_id]
            await event.reply("❌ Broadcast cancelled."); return
        success = failed = 0
        for uid in TOTAL_USERS:
            try: await self.bot.send_message(int(uid), event.message); success += 1; await asyncio.sleep(0.5)
            except: failed += 1
        await event.reply(f"📢 Broadcast Complete!\n\n✅ Success: {success}\n❌ Failed: {failed}", parse_mode='markdown')
        if user_id in self.user_states: del self.user_states[user_id]

async def main():
    for f in os.listdir('.'):
        if 'bot_session' in f and f.endswith(('.session', '.session-journal')):
            if f != f"{BOT_SESSION_NAME}.session" and f != f"{BOT_SESSION_NAME}.session-journal":
                try: os.remove(f); print(f"🗑️ {f}")
                except: pass
    
    print(f"""
╔══════════════════════════════════════╗
║  🤖 @LIKE CODE FETCHER v6.0        ║
║  🐲 Premium | 💾 Persistent Deposits║
║  📱 QR | 🌍 International OTP       ║
╚══════════════════════════════════════╝
    """)
    
    bot = AdvancedLikeBot()
    await bot.start()

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print("\n👋 Stopped")
    except Exception as e: print(f"\n❌ {e}")
