# Here's your full bot script converted to use **slash commands** via `discord.app_commands`.

import discord
from flask import Flask
import threading
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
import math
import re
import os
import json

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
user_reminders = {}

RESTRICTED_CHANNELS = [1334140159641255981, 1370660850712580106]
REMINDERS_FILE = 'reminders.json'

def load_reminders():
    global user_reminders
    if os.path.isfile(REMINDERS_FILE):
        with open(REMINDERS_FILE, 'r') as f:
            data = json.load(f)
        user_reminders = {int(uid): datetime.fromisoformat(ts) for uid, ts in data.items()}

def save_reminders():
    data = {str(uid): ts.isoformat() for uid, ts in user_reminders.items()}
    with open(REMINDERS_FILE, 'w') as f:
        json.dump(data, f)

def is_restricted(interaction: discord.Interaction):
    return interaction.channel_id in RESTRICTED_CHANNELS

@bot.event
async def on_ready():
    load_reminders()
    if not save_reminder_task.is_running():
        save_reminder_task.start()
    if not check_reminders.is_running():
        check_reminders.start()
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")

@tree.command(name="price", description="Shows the Robux price chart.")
async def price(interaction: discord.Interaction):
    if is_restricted(interaction):
        await interaction.response.send_message("❌ This command cannot be used in this channel.", ephemeral=True)
        return
    embed = discord.Embed(title="Robux Price Chart", color=discord.Color.magenta())
    embed.set_image(url="https://media.discordapp.net/attachments/1334539367859097620/1370629440140476547/qocZRkq.jpg")
    embed.set_footer(text="Prices subject to change • Payment via Bkash only")
    await interaction.response.send_message(embed=embed)

@tree.command(name="groups", description="Lists required Roblox groups for Robux.")
async def groups(interaction: discord.Interaction):
    if is_restricted(interaction):
        await interaction.response.send_message("❌ This command cannot be used in this channel.", ephemeral=True)
        return
    embed = discord.Embed(title="🤝 Join Our Roblox Groups", description="Joining the groups is **required** to receive Robux.", color=discord.Color.green())
    embed.add_field(name="**1 🔹 RoTech Studio**", value="[Click to Join](https://www.roblox.com/communities/5365937/RoTech-Studio#!/about)", inline=False)
    embed.add_field(name="**2 🔹 don't read the groups description**", value="[Click to Join](https://www.roblox.com/communities/35455005/dont-read-the-groups-description#!/about)", inline=False)
    embed.set_footer(text="⏳ Stay in the groups for 2 weeks before buying. Use `/remind` to get reminded.")
    await interaction.response.send_message(embed=embed)

@tree.command(name="remind", description="Set a 15-day reminder for Robux eligibility.")
async def remind(interaction: discord.Interaction):
    if is_restricted(interaction):
        await interaction.response.send_message("❌ This command cannot be used in this channel.", ephemeral=True)
        return
    user_id = interaction.user.id
    now = datetime.utcnow()

    if user_id in user_reminders:
        joined_date = user_reminders[user_id]
        days_passed = (now - joined_date).days
        days_remaining = max(0, 15 - days_passed)
        dm_date = (joined_date + timedelta(days=15)).strftime('%B %d, %Y')
        await interaction.response.send_message(
            f"🔸 You are `{days_remaining} days` away from being eligible if you joined on {joined_date.strftime('%B %d, %Y')}. You will be DMed on {dm_date}."
        )
    else:
        user_reminders[user_id] = now
        save_reminders()
        await interaction.response.send_message("✅ **You will be DMed by the bot after 15 days to remind you!**")

@tree.command(name="setremind", description="Admin: Set reminder for another user.")
@app_commands.describe(member="The member to remind")
@app_commands.checks.has_role(1334531528914370672)
async def setremind(interaction: discord.Interaction, member: discord.Member):
    if is_restricted(interaction):
        await interaction.response.send_message("❌ This command cannot be used in this channel.", ephemeral=True)
        return
    user_id = member.id
    now = datetime.utcnow()

    if user_id in user_reminders:
        joined_date = user_reminders[user_id]
        days_passed = (now - joined_date).days
        days_remaining = max(0, 15 - days_passed)
        dm_date = (joined_date + timedelta(days=15)).strftime('%B %d, %Y')
        await interaction.response.send_message(
            f"{member.mention} 🔸 You are `{days_remaining} days` away if you joined on {joined_date.strftime('%B %d, %Y')}. You will be DMed on {dm_date}."
        )
    else:
        user_reminders[user_id] = now
        save_reminders()
        await interaction.response.send_message(f"{member.mention} ✅ **will be DMed after 15 days to remind them about the purchase!**")

@tree.command(name="convert", description="Convert between Taka and Robux")
@app_commands.describe(input="Example: 199tk or 450 robux")
async def convert(interaction: discord.Interaction, input: str):
    if is_restricted(interaction):
        await interaction.response.send_message("❌ This command cannot be used in this channel.", ephemeral=True)
        return

    input = input.lower().replace(" ", "")
    amount_match = re.search(r'(\d+)', input)

    if not amount_match:
        await interaction.response.send_message("❌ Please provide a valid amount.")
        return

    amount = int(amount_match.group(1))

    if any(x in input for x in ['tk', 'bdt', 'taka']):
        if amount < 499:
            if amount < 99:
                await interaction.response.send_message("❌ The minimum amount you can buy with is **99tk**, which gives **110 Robux**.")
            elif amount < 199:
                await interaction.response.send_message("You can buy the **110 Robux for 99tk** package.")
            elif amount < 299:
                await interaction.response.send_message(f"You can buy one the following packages:\n-**110 Robux for 99tk**\n-**225 Robux for 199tk**")
            elif amount < 399:
                await interaction.response.send_message(f"You can buy one the following packages:\n-**225 Robux for 199tk**\n-**335 Robux for 299tk**")
            else:
                await interaction.response.send_message(f"You can buy one the following packages:\n-**450 Robux for 399tk**\n-**650 Robux for 499tk**")
        else:
            robux = math.ceil(amount * 1.3)
            await interaction.response.send_message(f"You will get **{robux} Robux** for {amount}tk.")

    elif any(x in input for x in ['rbx', 'robux', 'r$', 'rs', 'roblox', 'rb']):
        packages = {110: 99, 225: 199, 335: 299, 450: 399, 650: 499}
        sorted_robux = sorted(packages)

        if amount < 650:
            # Find closest lower and upper package
            lower = None
            upper = None
            for r in sorted_robux:
                if r < amount:
                    lower = r
                elif r >= amount and upper is None:
                    upper = r

            package_lines = ["You can buy one of the following packages:"]
            if lower:
                package_lines.append(f"- **{lower} Robux for {packages[lower]}tk**")
            if upper:
                package_lines.append(f"- **{upper} Robux for {packages[upper]}tk**")

            await interaction.response.send_message("\n".join(package_lines))
        else:
            taka = math.ceil(amount / 1.3)
            await interaction.response.send_message(f"{amount} Robux will cost you **{taka}tk**.")

    else:
        await interaction.response.send_message("❌ Please include a valid currency format like `taka`, `tk`, `bdt`, `robux`, `rbx`, `r$`")

@tree.command(name="help", description="List all available commands")
async def help(interaction: discord.Interaction):
    if is_restricted(interaction):
        await interaction.response.send_message("❌ This command cannot be used in this channel.", ephemeral=True)
        return

    embed = discord.Embed(title="📜 Available Commands", description="Here's a list of slash commands you can use:", color=discord.Color.blue())
    embed.add_field(name="💱 `/convert <amount><currency>`", value="Convert between **Taka and Robux**.\nExamples: • `199tk` • `450 robux`", inline=False)
    embed.add_field(name="🧾 `/price`", value="Shows the current **Robux price chart**.", inline=False)
    embed.add_field(name="🤝 `/groups`", value="Lists the **Roblox groups** you must join to receive Robux.", inline=False)
    embed.add_field(name="⏰ `/remind`", value="Sets a **15-day reminder** after you join the required groups to become eligible for Robux.", inline=False)
    embed.set_footer(text="Note: Some commands are restricted to specific channels or roles.")
    await interaction.response.send_message(embed=embed)

@tasks.loop(minutes=60)
async def check_reminders():
    now = datetime.utcnow()
    to_remove = []
    for user_id, remind_time in user_reminders.items():
        if now - remind_time >= timedelta(days=15):
            user = await bot.fetch_user(user_id)
            try:
                await user.send("📩 You should be eligible for a robux purchase now in RSBD! Open a ticket at https://discord.com/channels/1334140159012241410/1334535165187326053 to buy.")
            except:
                pass
            to_remove.append(user_id)
    for uid in to_remove:
        del user_reminders[uid]
    if to_remove:
        save_reminders()

@tasks.loop(minutes=10)
async def save_reminder_task():
    save_reminders()

# Keep Alive
app = Flask('')

@app.route('/')
def home():
    return 'Bot is running!'

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()

keep_alive()

bot.run(os.environ['DISCORD_TOKEN'])
