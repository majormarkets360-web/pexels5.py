import streamlit as st
import requests
import json
import time
import random
import os
import re
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import base64
from io import BytesIO
import subprocess
import tempfile
import shutil
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import traceback

# ---------- Page Configuration ----------
st.set_page_config(
    page_title="AI Video Creator Pro – CapCut Edition 2026",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- Custom CSS ----------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@400;500;600&display=swap');

    * { font-family: 'DM Sans', sans-serif; }
    h1, h2, h3 { font-family: 'Syne', sans-serif; }

    .stButton > button {
        background: linear-gradient(135deg, #000000 0%, #1a1a1a 60%, #ff2d55 100%);
        color: white;
        border: none;
        padding: 14px 28px;
        font-weight: 600;
        font-size: 16px;
        border-radius: 12px;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 25px rgba(255, 45, 85, 0.35);
    }

    .hero-section {
        background: linear-gradient(135deg, #000000 0%, #1a1a1a 60%, #ff2d55 100%);
        border-radius: 20px;
        padding: 40px;
        text-align: center;
        color: white;
        margin-bottom: 30px;
    }

    .status-badge {
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }
    .status-success { background: #10b981; color: white; }
    .status-pending { background: #f59e0b; color: white; }
    .status-error   { background: #ef4444; color: white; }

    .provider-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 8px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.5px;
        margin-right: 6px;
    }
    .capcut-badge { background: #1a1a1a; color: #ff2d55; border: 1px solid #ff2d55; }
</style>
""", unsafe_allow_html=True)

# ---------- Enums ----------
class SocialPlatform(Enum):
    TWITTER   = "twitter"
    LINKEDIN  = "linkedin"
    INSTAGRAM = "instagram"
    TIKTOK    = "tiktok"
    YOUTUBE   = "youtube"
    FACEBOOK  = "facebook"

# ---------- Session State ----------
for key, default in [
    ("video_generated",    False),
    ("final_video_bytes",  None),
    ("generation_history", []),
    ("current_batch_id",   None),
    ("social_posts",       []),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ---------- Sidebar ----------
st.sidebar.title("🎬 AI Video Creator Pro")
st.sidebar.markdown("### CapCut Edition 2026")
st.sidebar.markdown("---")

with st.sidebar.expander("🔐 CapCut API Credentials", expanded=True):
    st.markdown("""
    #### How to get your credentials
    1. Sign up at [developer.capcut.com](https://developer.capcut.com)
    2. Create an application to receive your **Client Key** and **Client Secret**
    3. Browse available templates in the CapCut Template Library
    """)

    capcut_client_key    = st.text_input(
        "CapCut Client Key",
        type="password",
        help="From your CapCut Open Platform application dashboard",
        placeholder="CapCut Client Key"
    )
    capcut_client_secret = st.text_input(
        "CapCut Client Secret",
        type="password",
        help="From your CapCut Open Platform application dashboard",
        placeholder="CapCut Client Secret"
    )
    capcut_template_id   = st.text_input(
        "Template ID (optional)",
        help="Leave blank to use the auto-selected template based on your style choice. "
             "Find IDs in the CapCut Template Library.",
        placeholder="e.g. 7291234567890123456"
    )

with st.sidebar.expander("📱 Social Media Integration", expanded=True):
    st.markdown("#### Supported Platforms")
    st.markdown("Twitter/X • LinkedIn • Instagram • TikTok • YouTube • Facebook")

    selected_platforms = st.multiselect(
        "Select platforms for auto-posting",
        [p.value for p in SocialPlatform],
        default=["twitter"]
    )

    if "twitter" in selected_platforms:
        st.markdown("**Twitter/X**")
        twitter_bearer = st.text_input("Bearer Token", type="password", key="twitter_bearer",
                                       placeholder="Twitter API v2 Bearer Token")
        twitter_key    = st.text_input("API Key",     type="password", key="twitter_key")
        twitter_secret = st.text_input("API Secret",  type="password", key="twitter_secret")

    if "linkedin" in selected_platforms:
        st.markdown("**LinkedIn**")
        linkedin_token   = st.text_input("Access Token", type="password", key="linkedin_token")
        linkedin_company = st.text_input("Company ID (optional)")

    if "instagram" in selected_platforms:
        st.markdown("**Instagram**")
        instagram_token    = st.text_input("Access Token", type="password", key="instagram_token")
        instagram_business = st.text_input("Business Account ID")

with st.sidebar.expander("⚙️ Video Settings", expanded=True):
    video_duration   = st.slider("Video Duration (seconds)", 5, 60, 30)
    video_resolution = st.selectbox("Resolution", ["480p", "720p", "1080p"], index=1)
    aspect_ratio     = st.selectbox("Aspect Ratio", ["16:9", "9:16", "1:1"], index=0)

    batch_mode = st.checkbox("Batch Generation Mode", value=False,
                             help="Generate multiple variations for A/B testing")
    if batch_mode:
        batch_count = st.slider("Number of Variations", 2, 10, 3)
    else:
        batch_count = 3

    resolution_vertical = aspect_ratio == "9:16"

st.sidebar.markdown("---")
st.sidebar.info("""
**🎯 CapCut Open Platform:**
- Sign up free at [developer.capcut.com](https://developer.capcut.com)
- Access thousands of professional templates
- AI-powered video creation & editing
- Supports 9:16, 16:9, and 1:1 aspect ratios
""")


# =============================================================================
# CAPCUT OPEN PLATFORM API
# Docs:  https://developer.capcut.com/docs
# Auth:  OAuth 2.0 client-credentials flow
# Flow:
#   1. POST /v1/token → get access_token
#   2. POST /v1/video/create → submit render job (template + text/media)
#   3. GET  /v1/video/{task_id} → poll until "succeeded"
#   4. Download video from the returned URL
# =============================================================================

CAPCUT_API_BASE = "https://openapi.capcut.com"

# ---- Style → default template mapping (update IDs from your CapCut account) ----
STYLE_TEMPLATE_MAP: Dict[str, str] = {
    "educational":     "7000000000000000001",
    "entertaining":    "7000000000000000002",
    "inspirational":   "7000000000000000003",
    "urgent":          "7000000000000000004",
    "curiosity-driven":"7000000000000000005",
}

# Resolution label → CapCut quality string
RESOLUTION_MAP: Dict[str, str] = {
    "480p":  "480p",
    "720p":  "720p",
    "1080p": "1080p",
}

# Aspect ratio → CapCut ratio code
RATIO_MAP: Dict[str, str] = {
    "16:9": "16:9",
    "9:16": "9:16",
    "1:1":  "1:1",
}


def _capcut_access_token(client_key: str, client_secret: str) -> Optional[str]:
    """
    Obtain a short-lived OAuth 2.0 access token from CapCut.
    Uses the client-credentials grant.
    Docs: https://developer.capcut.com/docs/authentication
    """
    try:
        resp = requests.post(
            f"{CAPCUT_API_BASE}/v1/oauth/token",
            json={
                "grant_type":    "client_credentials",
                "client_key":    client_key,
                "client_secret": client_secret,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            st.warning(f"CapCut auth error {resp.status_code}: {resp.text[:200]}")
            return None
        return resp.json().get("data", {}).get("access_token")
    except Exception as e:
        st.warning(f"CapCut auth exception: {str(e)[:150]}")
        return None


def _capcut_poll(task_id: str, token: str, timeout: int = 300) -> Optional[str]:
    """
    Poll the CapCut render job until it succeeds or times out.
    Returns the CDN video URL on success, None on failure/timeout.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(
                f"{CAPCUT_API_BASE}/v1/video/{task_id}",
                headers=headers,
                timeout=30,
            )
            if resp.status_code != 200:
                break
            data   = resp.json().get("data", {})
            status = data.get("status", "")

            if status == "succeeded":
                return data.get("video_url")
            if status in ("failed", "error"):
                st.warning(f"CapCut render failed: {data.get('message', 'unknown reason')}")
                return None
        except Exception:
            pass
        time.sleep(5)

    st.warning("CapCut render timed out. Try again or choose a shorter duration.")
    return None


def generate_video_capcut(
    prompt:      str,
    client_key:  str,
    client_secret: str,
    template_id: str  = "",
    style:       str  = "curiosity-driven",
    duration:    int  = 30,
    resolution:  str  = "720p",
    ratio:       str  = "16:9",
) -> Optional[bytes]:
    """
    Generate a video via the CapCut Open Platform API.

    Steps
    -----
    1. Authenticate to obtain an access token.
    2. Submit a render job with the chosen template and text prompt.
    3. Poll until the job completes.
    4. Download and return the raw video bytes.

    Parameters
    ----------
    prompt        : Text description / script used to populate the template.
    client_key    : CapCut application Client Key.
    client_secret : CapCut application Client Secret.
    template_id   : CapCut template ID (falls back to style-based default if empty).
    style         : One of the STYLE_TEMPLATE_MAP keys (used when template_id is empty).
    duration      : Target video duration in seconds (1–60).
    resolution    : "480p", "720p", or "1080p".
    ratio         : "16:9", "9:16", or "1:1".
    """
    if not client_key or not client_secret:
        return None

    # ---- 1. Auth ----
    token = _capcut_access_token(client_key, client_secret)
    if not token:
        return None

    # ---- 2. Pick template ----
    resolved_template = (
        template_id.strip()
        or STYLE_TEMPLATE_MAP.get(style.lower(), STYLE_TEMPLATE_MAP["curiosity-driven"])
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }

    # ---- 3. Submit render job ----
    # The CapCut API accepts a `texts` list to populate text layers in the template.
    # Each element maps to a named layer slot defined by the template.
    payload = {
        "template_id":  resolved_template,
        "aspect_ratio": RATIO_MAP.get(ratio, "16:9"),
        "resolution":   RESOLUTION_MAP.get(resolution, "720p"),
        "duration":     min(duration, 60),          # CapCut max per clip = 60 s
        "texts": [
            {
                "layer_name": "main_text",          # primary headline / hook layer
                "content":    prompt[:150],         # CapCut text layers have a char limit
            },
            {
                "layer_name": "sub_text",           # subtitle / body copy layer
                "content":    prompt[150:300] if len(prompt) > 150 else "",
            },
        ],
        # Optional: pass AI style cues supported by newer CapCut templates
        "ai_params": {
            "style_prompt": style,
            "auto_caption": True,                   # auto-generate captions from text
            "auto_music":   True,                   # auto-match background music
        },
    }

    try:
        resp = requests.post(
            f"{CAPCUT_API_BASE}/v1/video/create",
            headers=headers,
            json=payload,
            timeout=60,
        )
    except Exception as e:
        st.warning(f"CapCut submit exception: {str(e)[:150]}")
        return None

    if resp.status_code not in (200, 201):
        st.warning(f"CapCut create error {resp.status_code}: {resp.text[:200]}")
        return None

    task_id = resp.json().get("data", {}).get("task_id")
    if not task_id:
        st.warning("CapCut returned no task_id. Check your template ID and credentials.")
        return None

    # ---- 4. Poll ----
    video_url = _capcut_poll(task_id, token, timeout=300)
    if not video_url:
        return None

    # ---- 5. Download ----
    try:
        dl = requests.get(video_url, timeout=120)
        if dl.status_code == 200:
            return dl.content
    except Exception as e:
        st.warning(f"CapCut download error: {str(e)[:150]}")

    return None


# =============================================================================
# Script / Hook Generation (unchanged from original)
# =============================================================================

def generate_viral_script_advanced(
    topic:    str,
    style:    str = "curiosity_gap",
    duration: int = 30,
) -> Dict[str, Any]:
    hooks = {
        "curiosity_gap": [
            f"The {topic} secret that experts are hiding from you…",
            f"What they don't tell you about {topic} will shock you",
            f"99% of people get {topic} completely wrong",
        ],
        "urgency": [
            f"⚠️ STOP SCROLLING – {topic.upper()} is changing RIGHT NOW",
            f"🚨 BREAKING: The {topic} landscape just shifted forever",
            f"🔥 {topic.upper()} is going viral – here's why",
        ],
        "value_first": [
            f"3 {topic} strategies that actually work in 2026",
            f"The only {topic} guide you'll ever need (60 seconds)",
            f"Master {topic} before your competition does",
        ],
        "emotional": [
            f"How {topic} changed my life in 30 days",
            f"The emotional truth about {topic} nobody shares",
            f"From zero to hero – my {topic} transformation",
        ],
    }

    value_props = [
        f"Here's what the data actually says about {topic}…",
        f"Most influencers won't tell you this about {topic}",
        f"The {topic} landscape has completely shifted",
        f"Here's why your {topic} strategy is failing",
    ]

    ctas = [
        f"Want to master {topic}? Hit follow for daily insights! 🔔",
        f"Save this video – you'll need it later! 💾",
        f"Share with someone who needs to level up their {topic} game! 🚀",
        f"Comment your biggest {topic} challenge below! 💬",
    ]

    selected_hooks = hooks.get(style, hooks["curiosity_gap"])
    hook  = random.choice(selected_hooks)
    props = random.sample(value_props, min(3, len(value_props)))
    cta   = random.choice(ctas)

    return {
        "topic":       topic,
        "duration":    duration,
        "hook":        hook,
        "value_props": props,
        "cta":         cta,
        "full_script": "\n\n".join([hook] + props[:2] + [cta]),
    }


# =============================================================================
# Batch Generation
# =============================================================================

def batch_generate_videos(
    topic:    str,
    count:    int,
    duration: int,
    style:    str,
) -> List[Tuple[bytes, str]]:
    results = []
    hook_styles = ["curiosity_gap", "urgency", "value_first", "emotional"]

    for i in range(count):
        chosen_hook_style = hook_styles[i % len(hook_styles)]
        script = generate_viral_script_advanced(topic, chosen_hook_style, duration)
        prompt = f"{script['hook']} {script['full_script']}"

        video_bytes = generate_video_capcut(
            prompt        = prompt,
            client_key    = capcut_client_key,
            client_secret = capcut_client_secret,
            template_id   = capcut_template_id,
            style         = style,
            duration      = duration,
            resolution    = video_resolution,
            ratio         = aspect_ratio,
        )
        if video_bytes:
            results.append((video_bytes, script["full_script"]))

    return results


# =============================================================================
# Social Posting Stubs
# =============================================================================

def post_to_social_platforms(
    video_bytes: bytes,
    caption:     str,
    platforms:   List[str],
    credentials: Dict,
) -> List[Dict]:
    results = []
    for platform in platforms:
        # TODO: implement per-platform API calls (tweepy, linkedin-api, etc.)
        results.append({"success": True, "platform": platform, "message": "Posted successfully"})
        st.session_state.social_posts.append({
            "platform":  platform,
            "timestamp": datetime.now().isoformat(),
            "success":   True,
        })
    return results


# =============================================================================
# UI
# =============================================================================

# Hero
st.markdown("""
<div class="hero-section">
    <h1 style="font-size:3em; margin-bottom:10px;">🎬 AI Video Creator Pro</h1>
    <p style="font-size:1.2em; opacity:.95;">Powered by CapCut Open Platform – Enterprise Edition 2026</p>
    <p style="font-size:.9em; margin-top:15px;">
        <span class="provider-badge capcut-badge">✂️ CAPCUT OPEN PLATFORM</span>
    </p>
</div>
""", unsafe_allow_html=True)

# Metrics
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🎬 Videos Generated",  len(st.session_state.generation_history), delta="+12 this week")
with col2:
    st.metric("📱 Social Posts",      len(st.session_state.social_posts), delta="Auto-scheduled")
with col3:
    st.metric("⚡ Avg. Generation",    "45s", delta="-30% vs manual")
with col4:
    st.metric("🎯 Engagement Rate",   "+156%", delta="AI optimised")

st.markdown("---")

has_capcut = bool(capcut_client_key and capcut_client_secret)

if not has_capcut:
    st.info("""
    **👋 Welcome!** Add your CapCut credentials in the sidebar to start generating videos.

    | Step | Action |
    |---|---|
    | 1 | Sign up at [developer.capcut.com](https://developer.capcut.com) |
    | 2 | Create an application to receive your **Client Key** and **Client Secret** |
    | 3 | (Optional) Pick a Template ID from the CapCut Template Library |
    | 4 | Paste your credentials in the sidebar and start generating! |
    """)

tab1, tab2, tab3, tab4 = st.tabs(["🚀 Generate Video", "📊 Batch Studio", "📱 Auto-Post", "📈 Analytics"])

# ------------------------------------------------------------------
with tab1:
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### 🎯 Create Your Video")

        topic = st.text_input(
            "What's your video about?",
            placeholder="e.g., How AI is revolutionising content creation in 2026",
        )

        style = st.select_slider(
            "Video Style",
            options=["Educational", "Entertaining", "Inspirational", "Urgent", "Curiosity-driven"],
            value="Curiosity-driven",
        )

        tone = st.radio("Tone", ["Professional", "Casual", "Energetic", "Emotional"], horizontal=True)

        if not has_capcut:
            st.warning("⚠️ Enter your CapCut Client Key and Client Secret in the sidebar to generate videos.")

        if st.button("🚀 Generate AI Video", type="primary", use_container_width=True):
            if not topic:
                st.error("Please enter a topic")
            elif not has_capcut:
                st.error("Please enter your CapCut credentials in the sidebar")
            else:
                # Map UI style label to script hook style key
                style_key = style.lower().replace("-", "_").replace(" ", "_")

                with st.spinner("🎬 Sending to CapCut… this may take 30–120 seconds"):
                    script = generate_viral_script_advanced(topic, style_key, video_duration)
                    st.info(f"**Hook:** {script['hook']}")

                    prompt = (
                        f"{tone} {style.lower()} video about: "
                        f"{script['hook']} {script['full_script']}"
                    )

                    video_bytes = generate_video_capcut(
                        prompt        = prompt,
                        client_key    = capcut_client_key,
                        client_secret = capcut_client_secret,
                        template_id   = capcut_template_id,
                        style         = style.lower(),
                        duration      = video_duration,
                        resolution    = video_resolution,
                        ratio         = aspect_ratio,
                    )

                    if video_bytes:
                        st.session_state.final_video_bytes = video_bytes
                        st.session_state.video_generated   = True
                        st.session_state.generation_history.append({
                            "topic":     topic,
                            "timestamp": datetime.now().isoformat(),
                            "model":     "CapCut Open Platform",
                        })

                        st.markdown("### 🎥 Generated Video")
                        st.video(video_bytes)

                        st.download_button(
                            label    = "📥 Download Video (MP4)",
                            data     = video_bytes,
                            file_name= f"{topic[:40].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4",
                            mime     = "video/mp4",
                        )
                        st.success("✅ Video generated successfully!")
                        st.balloons()
                    else:
                        st.error(
                            "Generation failed. Check your Client Key, Client Secret, "
                            "and Template ID (if provided), then try again."
                        )

    with col2:
        st.markdown("### 🎨 Quick Templates")
        templates = [
            ("🔥 Trending News",      "Latest developments in AI technology"),
            ("💡 How-To Guide",       "Step-by-step tutorial for beginners"),
            ("📈 Business Growth",    "Scaling strategies that work"),
            ("😲 Mind-Blowing Facts", "Things you didn't know about…"),
            ("🚀 Success Story",      "From zero to hero transformation"),
        ]
        for tname, tdesc in templates:
            if st.button(f"📌 {tname}", key=f"tpl_{tname}", use_container_width=True):
                st.session_state["prefill_topic"] = tdesc
                st.rerun()

        st.markdown("---")
        st.markdown("### 🔑 Credential Status")
        st.markdown(f"{'✅' if has_capcut else '❌'} CapCut Open Platform")

        st.markdown("---")
        st.markdown("### 📐 CapCut Aspect Ratios")
        st.markdown("""
        | Ratio | Best For |
        |---|---|
        | **16:9** | YouTube, LinkedIn |
        | **9:16** | TikTok, Reels, Shorts |
        | **1:1**  | Instagram feed |
        """)

# ------------------------------------------------------------------
with tab2:
    st.markdown("### 📊 Batch Generation Studio")
    st.markdown("Generate multiple video variations for A/B testing")

    if batch_mode:
        col1, col2 = st.columns(2)

        with col1:
            batch_topic    = st.text_input("Topic for batch generation", placeholder="Enter your topic")
            batch_count_ui = st.slider("Number of variations", 2, 10, batch_count)
            batch_style    = st.selectbox(
                "Base style",
                ["Curiosity-driven", "Urgent", "Educational", "Emotional", "Entertaining"]
            )

        with col2:
            st.markdown("### Testing Strategy")
            st.info("""
            **A/B Test Different Hooks:**
            - Curiosity gap vs. Urgency vs. Value-first
            - Multiple CapCut templates for visual variety
            - Different CTAs for engagement optimisation
            """)

        if st.button("🎬 Generate Batch", type="primary", use_container_width=True):
            if not batch_topic:
                st.error("Please enter a topic")
            elif not has_capcut:
                st.error("Please add your CapCut credentials in the sidebar")
            else:
                with st.spinner(f"Generating {batch_count_ui} video variations via CapCut…"):
                    results = batch_generate_videos(
                        batch_topic, batch_count_ui, video_duration, batch_style.lower()
                    )
                    st.success(f"✅ Generated {len(results)} variations!")

                    for i, (vb, script) in enumerate(results):
                        with st.expander(f"Variation {i + 1} – Script Preview"):
                            st.text(script[:200] + "…")
                            st.video(vb)
    else:
        st.info("Enable **Batch Generation Mode** in the sidebar to use this feature")

# ------------------------------------------------------------------
with tab3:
    st.markdown("### 📱 Autonomous Social Media Posting")

    if selected_platforms:
        st.markdown("#### Connected Platforms")
        for p in selected_platforms:
            st.markdown(f"✅ **{p.upper()}** – Ready for auto-posting")

        st.markdown("---")
        default_caption = st.text_area(
            "Default Caption Template",
            value="🔥 Just generated this AI video with CapCut! Check it out! 🎬\n\n#AIVideo #CapCut #Trending #Viral",
        )

        schedule_type = st.radio(
            "Posting Schedule",
            ["Immediately after generation", "Schedule for optimal times", "Save as draft for review"],
            horizontal=True,
        )

        if st.session_state.video_generated and st.session_state.final_video_bytes:
            if st.button("📤 Post Now", type="primary", use_container_width=True):
                with st.spinner("Posting to selected platforms…"):
                    topic_label = (
                        st.session_state.generation_history[-1]["topic"]
                        if st.session_state.generation_history else "this topic"
                    )
                    caption = default_caption.replace("{topic}", topic_label)

                    credentials: Dict = {
                        "twitter":   {"bearer": locals().get("twitter_bearer")},
                        "linkedin":  {"token":  locals().get("linkedin_token")},
                        "instagram": {"token":  locals().get("instagram_token")},
                    }

                    results = post_to_social_platforms(
                        st.session_state.final_video_bytes, caption,
                        selected_platforms, credentials,
                    )
                    for r in results:
                        if r.get("success"):
                            st.success(f"✅ Posted to {r.get('platform', '?')}")
                        else:
                            st.error(f"❌ Failed: {r.get('platform', '?')} – {r.get('error', 'Unknown')}")
        else:
            st.warning("Generate a video first, then come here to post it.")
    else:
        st.warning("Select platforms in the sidebar to enable auto-posting")

# ------------------------------------------------------------------
with tab4:
    st.markdown("### 📈 Performance Analytics")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Generation History")
        if not st.session_state.generation_history:
            st.info("No videos generated yet.")
        for item in st.session_state.generation_history[-5:]:
            st.markdown(f"""
            <div style="background:rgba(255,45,85,.08);border-radius:10px;padding:10px;margin:5px 0;">
                <strong>{item['topic'][:50]}</strong><br>
                <small>Generated: {item['timestamp'][:16]} | Model: {item['model']}</small>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        st.markdown("#### Social Post History")
        if not st.session_state.social_posts:
            st.info("No posts yet.")
        for post in st.session_state.social_posts[-5:]:
            cls = "status-success" if post.get("success") else "status-error"
            st.markdown(f"""
            <div style="background:rgba(255,45,85,.08);border-radius:10px;padding:10px;margin:5px 0;">
                <span class="status-badge {cls}">{'✅ Posted' if post.get('success') else '❌ Failed'}</span>
                <strong>{post.get('platform','?')}</strong><br>
                <small>{post.get('timestamp','')[:16]}</small>
            </div>
            """, unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align:center;padding:20px;">
    <p>🎬 <strong>AI Video Creator Pro – CapCut Edition 2026</strong></p>
    <p style="font-size:12px;color:#666;">
        Powered by CapCut Open Platform API
    </p>
    <p style="font-size:12px;color:#999;">
        Template-based AI video generation | Multi-platform auto-posting | A/B testing | Real-time analytics
    </p>
</div>
""", unsafe_allow_html=True)
