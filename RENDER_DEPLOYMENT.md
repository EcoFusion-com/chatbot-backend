# Render Deployment Guide for Eco Fusion Chatbot

This guide will help you deploy the Eco Fusion Chatbot to Render.com successfully.

## 🚀 Quick Deployment

### 1. Repository Setup
- **Repository**: `https://github.com/EcoFusion-com/chatbot-backend`
- **Branch**: `main`
- **Root Directory**: `/` (root of repository)

### 2. Render Service Configuration

#### **Service Type**: Web Service
- **Name**: `eco-fusion-chatbot`
- **Environment**: `Python 3`
- **Region**: `Oregon` (or your preferred region)
- **Plan**: `Starter` (free tier)

#### **Build & Deploy Settings**
- **Build Command**: 
  ```bash
  pip install --upgrade pip && pip install -r requirements.txt && rasa train
  ```
- **Start Command**: 
  ```bash
  rasa run --enable-api --cors "*" --port $PORT
  ```

#### **Environment Variables**
Set these in your Render dashboard:

```env
# Required
PYTHON_VERSION=3.10.12
RASA_ENVIRONMENT=production
LOG_LEVEL=INFO

# Optional (if you have them)
HF_TOKEN=your_hugging_face_token_here
ADMIN_EMAIL=your_admin_email@example.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_smtp_username
SMTP_PASS=your_smtp_password
GOOGLE_CALENDAR_API_KEY=your_google_calendar_api_key
CRM_WEBHOOK_URL=https://your-crm-webhook.com/api/lead
```

## 🔧 Troubleshooting

### **Python Version Issues**
If you encounter Python version compatibility issues:

1. **Check Python Version**: Ensure you're using Python 3.10.12
2. **Update runtime.txt**: The file specifies `python-3.10.12`
3. **Verify Dependencies**: All packages are compatible with Python 3.10

### **Rasa Installation Issues**
If Rasa installation fails:

1. **Check Requirements**: Ensure all dependencies are compatible
2. **Update Versions**: Use the updated `requirements.txt` with version ranges
3. **Clear Cache**: Try redeploying with a clean build

### **Model Training Issues**
If model training fails:

1. **Check Data**: Ensure all training data files are present
2. **Validate Data**: Run `rasa data validate` locally first
3. **Check Logs**: Review build logs for specific errors

### **Server Startup Issues**
If the server doesn't start:

1. **Check Port**: Ensure `$PORT` environment variable is set
2. **Check CORS**: Verify CORS settings are correct
3. **Check Logs**: Review startup logs for errors

## 📋 Pre-Deployment Checklist

- [ ] **Repository**: Code is pushed to GitHub
- [ ] **Python Version**: 3.10.12 specified in `runtime.txt`
- [ ] **Dependencies**: `requirements.txt` updated with compatible versions
- [ ] **Environment Variables**: All required variables set in Render
- [ ] **Training Data**: All Rasa training files present
- [ ] **Build Command**: Correct build command configured
- [ ] **Start Command**: Correct start command configured

## 🚀 Deployment Steps

### **Step 1: Create Render Service**
1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Select `EcoFusion-com/chatbot-backend`

### **Step 2: Configure Service**
1. **Name**: `eco-fusion-chatbot`
2. **Environment**: `Python 3`
3. **Region**: `Oregon` (or preferred)
4. **Branch**: `main`
5. **Root Directory**: `/` (leave empty)

### **Step 3: Set Build & Deploy**
1. **Build Command**:
   ```bash
   pip install --upgrade pip && pip install -r requirements.txt && rasa train
   ```
2. **Start Command**:
   ```bash
   rasa run --enable-api --cors "*" --port $PORT
   ```

### **Step 4: Set Environment Variables**
Add all required environment variables in the Render dashboard.

### **Step 5: Deploy**
1. Click "Create Web Service"
2. Wait for build to complete
3. Check logs for any errors
4. Test the deployed service

## 🧪 Testing Deployment

### **Health Check**
```bash
curl https://your-app-name.onrender.com/status
```

### **Test Chatbot**
```bash
curl -X POST https://your-app-name.onrender.com/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{"sender": "test", "message": "Hello"}'
```

### **Check Logs**
- Go to Render Dashboard
- Click on your service
- Go to "Logs" tab
- Check for any errors

## 🔄 Updates and Maintenance

### **Updating Code**
1. Push changes to GitHub
2. Render will automatically redeploy
3. Check logs for any issues

### **Updating Dependencies**
1. Update `requirements.txt`
2. Push changes to GitHub
3. Render will reinstall dependencies
4. Check logs for compatibility issues

### **Monitoring**
- **Uptime**: Check Render dashboard for service status
- **Logs**: Monitor logs for errors and performance
- **Metrics**: Use Render's built-in metrics

## 📞 Support

If you encounter issues:

1. **Check Logs**: Review Render build and runtime logs
2. **Test Locally**: Ensure the app works locally first
3. **Update Dependencies**: Ensure all packages are compatible
4. **Contact Support**: Use Render's support channels

## 🎯 Success Indicators

Your deployment is successful when:

- ✅ **Build Completes**: No errors during build process
- ✅ **Server Starts**: Rasa server starts successfully
- ✅ **Health Check Passes**: `/status` endpoint returns 200
- ✅ **Chatbot Responds**: Webhook endpoint accepts messages
- ✅ **Logs Clean**: No critical errors in logs

---

**Happy Deploying! 🚀**

*For more help, check the [Render Documentation](https://render.com/docs) or contact the Eco Fusion team.*
