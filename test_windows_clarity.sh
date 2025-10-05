#!/bin/bash
# Example: Using Windows Voice Control with Clearer Voice
# This script demonstrates how to use the kathleen-high voice for better Windows recognition

echo "🎤 Windows Voice Control - Clarity Test"
echo "========================================"
echo ""

# Check if environment is set
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Creating from example..."
    cp windows_voice_control.env.example .env
    
    # Enable clearer voice by default
    echo "" >> .env
    echo "# Enable clearer voice for Windows" >> .env
    echo "USE_DIRECT_PIPER=true" >> .env
    
    echo "✅ Created .env file with clearer voice enabled"
fi

# Load environment
source .env

echo "📋 Current Configuration:"
echo "   Voice Model: ${PIPER_VOICE_MODEL:-en_US-kathleen-high}"
echo "   Length Scale: ${PIPER_LENGTH_SCALE:-1.1}"
echo "   Volume Boost: ${PIPER_VOLUME_BOOST:-1.0}"
echo "   Direct Piper: ${USE_DIRECT_PIPER:-false}"
echo ""

# Test if sox or ffmpeg is available for volume boost
if command -v sox &> /dev/null; then
    echo "✅ sox found - Volume boost available"
elif command -v ffmpeg &> /dev/null; then
    echo "✅ ffmpeg found - Volume boost available"
else
    echo "⚠️  sox/ffmpeg not found - Volume boost disabled"
    echo "   Install with: sudo apt-get install sox"
fi

echo ""
echo "🧪 Testing Commands:"
echo ""

# Test 1: Simple command
echo "1. Testing: 'Open Notepad'"
python3 windows_voice_control.py "Open Notepad"

if [ $? -eq 0 ]; then
    echo "   ✅ Command sent successfully"
else
    echo "   ❌ Command failed"
fi

sleep 2

# Test 2: Typing text
echo ""
echo "2. Testing: Type 'Hello Windows'"
python3 windows_voice_control.py --type "Hello Windows"

if [ $? -eq 0 ]; then
    echo "   ✅ Command sent successfully"
else
    echo "   ❌ Command failed"
fi

sleep 2

# Test 3: Keystroke
echo ""
echo "3. Testing: Press Enter"
python3 windows_voice_control.py --key Enter

if [ $? -eq 0 ]; then
    echo "   ✅ Command sent successfully"
else
    echo "   ❌ Command failed"
fi

echo ""
echo "🎉 Test completed!"
echo ""
echo "💡 Tips for best results:"
echo "   • Ensure Windows Voice Assistant is listening"
echo "   • Check audio cable connection"
echo "   • Adjust PIPER_LENGTH_SCALE if commands are missed (try 1.2 or 1.3)"
echo "   • Increase PIPER_VOLUME_BOOST if Windows doesn't hear (try 1.5)"
echo ""
echo "📚 For more help, see:"
echo "   • WINDOWS_VOICE_CLARITY_GUIDE.md - Detailed clarity configuration"
echo "   • WINDOWS_VOICE_CONTROL_QUICK_REF.md - Command reference"
echo "   • WINDOWS_VOICE_ASSIST_SETUP.md - Complete setup guide"
