# 🚀 Terabox Leech Bot with Verification & Auto-Forward  

A powerful Telegram bot with shortlink verification system and automatic file forwarding for Terabox file leeching.

## ✨ Features

### Phase 1: Verification System (Current)
- ✅ 3 free leech attempts (simulated)  
- ✅ Shortlink verification after 3 attempts
- ✅ Unlimited access after verification
- ✅ MongoDB user tracking
- ✅ Auto-forward all files to backup channel
- ✅ Admin statistics and management

### Phase 2: Real Terabox Leeching (Coming Soon)
- 🔄 Actual Terabox file downloading
- 🔄 Multiple file format support
- 🔄 Progress tracking
- 🔄 Advanced file management

## 🛠️ Setup

### 1. Prerequisites
- Python 3.11+
- MongoDB database
- Telegram bot token
- Shortlink service (like short.io, gplinks, etc.)
- Telegram channel for auto-forwarding

### 2. Installation
git clone https://github.com/yourusername/terabox-leech-bot
cd terabox-leech-bot
pip install -r requirements.txt
cp .env.example .env
### 3. Environment Variables
| Variable | Description | Required |
|----------|-------------|----------|
| `BOT_TOKEN` | Bot token from @BotFather | ✅ |
| `BOT_USERNAME` | Your bot username | ✅ |
| `OWNER_ID` | Your Telegram user ID | ✅ |
| `MONGODB_URL` | MongoDB connection string | ✅ |
| `BACKUP_CHANNEL_ID` | Channel ID for auto-forward | ✅ |
| `SHORTLINK_API` | Shortlink service API key | ✅ |
| `SHORTLINK_URL` | Shortlink service URL | ✅ |

### 4. Bot Setup
1. Create bot with @BotFather
2. Create MongoDB database
3. Create channel for auto-forwarding
4. Add bot as admin to channel
5. Get channel ID and add to config
6. Deploy on Koyeb/Railway/Heroku

## 📱 Commands

### User Commands
- `/start` - Start the bot
- `/help` - Get help
- `/leech` - Make leech attempt
- `/stats` - Check stats

### Admin Commands  
- `/testforward` - Test auto-forward system

## 🚀 Deployment on Koyeb

1. Fork this repository
2. Connect repository to Koyeb
3. Add environment variables in Koyeb dashboard
4. Deploy!

## 📈 How It Works

1. **User Registration**: New users get 3 free attempts
2. **Leech Simulation**: Users can make leech attempts (simulated)
3. **Auto-Forward**: All leeched files forwarded to backup channel
4. **Verification Required**: After 3 attempts, verification needed
5. **Unlimited Access**: Verified users get unlimited attempts

## 🔧 Advanced Configuration

### Auto-Forward Settings
- Enable/disable with `AUTO_FORWARD_ENABLED`
- Configure backup channel with `BACKUP_CHANNEL_ID`
- Customize forward message template in config

### Verification Settings
- Adjust free limit with `FREE_LEECH_LIMIT`
- Set token timeout with `VERIFY_TOKEN_TIMEOUT`
- Customize verification messages

## 📊 Statistics

Bot tracks:
- Total users
- Verified users  
- Total leech attempts
- Auto-forward success rate

## 🔒 Security

- User data encrypted in MongoDB
- Verification tokens expire automatically
- Admin commands restricted by user ID
- Safe auto-forward with error handling

## 📝 License

MIT License - see LICENSE file for details

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Create Pull Request

## 📞 Support

- Create an issue for bugs
- Discussion for feature requests
- Contact: [Your Contact Info]

---

**⭐ Star this repository if you found it helpful!**
