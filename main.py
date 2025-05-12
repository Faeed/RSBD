import discord
import asyncio
import math
import re
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from flask import Flask
import threading
import os
import json

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # For welcome messages

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)
user_reminders = {}

# Channels where commands should not work
restricted_channels = [1334140159641255981, 1370660850712580106]

# File path for persistence
REMINDERS_FILE = 'reminders.json'

def load_reminders():
    global user_reminders
    if os.path.isfile(REMINDERS_FILE):
        with open(REMINDERS_FILE, 'r') as f:
            data = json.load(f)
        # convert ISO strings back to datetime
        user_reminders = {int(uid): datetime.fromisoformat(ts)
                          for uid, ts in data.items()}

def save_reminders():
    # convert datetimes to ISO strings
    data = {str(uid): ts.isoformat() for uid, ts in user_reminders.items()}
    with open(REMINDERS_FILE, 'w') as f:
        json.dump(data, f)

@bot.event
async def on_ready():
    load_reminders()
    if not save_reminder_task.is_running():
        save_reminder_task.start()
    if not check_reminders.is_running():
        check_reminders.start()
    print(f'✅ Logged in as {bot.user}')

def is_restricted(ctx):
    return ctx.channel.id in restricted_channels

@bot.command()
async def price(ctx):
    if is_restricted(ctx):
        response = await ctx.send("❌ This command cannot be used in this channel.")
        await asyncio.sleep(5)
        await ctx.message.delete()
        await response.delete()
        return

    embed = discord.Embed(title="Robux Price Chart", color=discord.Color.magenta())
    embed.set_image(url="https://media.discordapp.net/attachments/1334539367859097620/1370629440140476547/qocZRkq.jpg")
    embed.set_footer(text="Prices subject to change • Payment via Bkash only")
    await ctx.send(embed=embed)

@bot.command(aliases=["group", "grouplinks"])
async def groups(ctx):
    if is_restricted(ctx):
        response = await ctx.send("❌ This command cannot be used in this channel.")
        await asyncio.sleep(5)
        await ctx.message.delete()
        await response.delete()
        return

    embed = discord.Embed(
        title="🤝 Join Our Roblox Groups",
        description="Joining the groups is **required** to receive Robux.",
        color=discord.Color.green())
    embed.add_field(
        name="**1 🔹 RoTech Studio**",
        value="[Click to Join](https://www.roblox.com/communities/5365937/RoTech-Studio#!/about)",
        inline=False)
    embed.add_field(
        name="**2 🔹 don't read the groups description**",
        value="[Click to Join](https://www.roblox.com/communities/35455005/dont-read-the-groups-description#!/about)",
        inline=False)
    embed.set_footer(
        text="⏳ Stay in the groups for 2 weeks before buying. After joining, use `!remind` to set your 15-day reminder.")
    await ctx.send(embed=embed)

@bot.command(name="remind")
async def remindme(ctx):
    if is_restricted(ctx):
        response = await ctx.send("❌ This command cannot be used in this channel.")
        await asyncio.sleep(5)
        await ctx.message.delete()
        await response.delete()
        return

    user_id = ctx.author.id
    now = datetime.utcnow()

    if user_id in user_reminders:
        joined_date = user_reminders[user_id]
        days_passed = (now - joined_date).days
        days_remaining = max(0, 15 - days_passed)
        dm_date = (joined_date + timedelta(days=15)).strftime('%B %d, %Y')
        await ctx.send(
            f"🔸 You are `{days_remaining} days` away from being eligible if you joined on {joined_date.strftime('%B %d, %Y')}. You will be DMed on {dm_date}."
        )
    else:
        user_reminders[user_id] = now
        save_reminders()
        await ctx.send("✅ **You will be DMed by the bot after 15 days to remind you!**")

@tasks.loop(minutes=60)
async def check_reminders():
    now = datetime.utcnow()
    to_remove = []
    for user_id, remind_time in user_reminders.items():
        if now - remind_time >= timedelta(days=15):
            user = await bot.fetch_user(user_id)
            try:
                await user.send(
                    "📩 You should be eligible for a robux purchase now in RSBD! Open a ticket at https://discord.com/channels/1334140159012241410/1334535165187326053 to buy."
                )
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

@bot.command(name="setremind")
@commands.has_role(1334531528914370672)
async def setremind(ctx, member: discord.Member):
    if is_restricted(ctx):
        response = await ctx.send("❌ This command cannot be used in this channel.")
        await asyncio.sleep(5)
        await ctx.message.delete()
        await response.delete()
        return

    user_id = member.id
    now = datetime.utcnow()

    if user_id in user_reminders:
        joined_date = user_reminders[user_id]
        days_passed = (now - joined_date).days
        days_remaining = max(0, 15 - days_passed)
        dm_date = (joined_date + timedelta(days=15)).strftime('%B %d, %Y')
        await ctx.send(
            f"{member.mention} 🔸 You are `{days_remaining} days` away if you joined on {joined_date.strftime('%B %d, %Y')}. You will be DMed on {dm_date}."
        )
    else:
        user_reminders[user_id] = now
        save_reminders()
        await ctx.send(f"{member.mention} ✅ **will be DMed after 15 days to remind them about the purchase!**")

@bot.command()
async def convert(ctx, *, input: str):
    if is_restricted(ctx):
        response = await ctx.send("❌ This command cannot be used in this channel.")
        await asyncio.sleep(5)
        await ctx.message.delete()
        await response.delete()
        return

    input = input.lower().replace(" ", "")
    amount_match = re.search(r'(\d+)', input)

    if not amount_match:
        await ctx.send("❌ Please provide a valid amount.")
        return

    amount = int(amount_match.group(1))

    # Taka to Robux (ntk/nbdt etc.)
    if any(x in input for x in ['tk', 'bdt', 'taka']):
        if amount < 500:
            if amount < 99:
                await ctx.send("❌ The minimum amount you can buy with is **99tk**, which gives **110 Robux**.")
            elif amount < 199:
                await ctx.send("You can buy the **110 Robux for 99tk** package.")
            elif amount < 299:
                await ctx.send("You can buy the **110 Robux for 99tk** or **225 Robux for 199tk** packages.")
            elif amount < 399:
                await ctx.send("You can buy the **225 Robux for 199tk** or **335 Robux for 299tk** packages.")
            else:
                await ctx.send("You can buy the **450 Robux for 399** or **650 Robux for 499** packages.")
        else:
            # Use conversion rate 1tk = 1.3 robux
            robux = math.ceil(amount * 1.3)
            await ctx.send(f"For **{amount}tk**, you will receive **{robux} Robux**.")


    # Robux to Taka (nrbx/nrobux/etc.)
    elif any(x in input for x in ['rbx', 'robux', 'r$', 'rs', 'roblox']):
        if amount < 650:
            # Use packages
            packages = {
                110: 99,
                225: 199,
                335: 299,
                450: 399
            }
            best_match = None
            for robux_amt in sorted(packages.keys()):
                if amount <= robux_amt:
                    best_match = robux_amt
                    break
            if best_match:
                cost = packages[best_match]
                await ctx.send(f"For **{amount} Robux**, you can buy the **{best_match} Robux package for {cost}tk**.")
            else:
                await ctx.send("❌ No available package for that amount.")
        else:
            # Use conversion rate
            taka = math.ceil(amount / 1.3)
            await ctx.send(f"For **{amount} Robux**, it will cost you **{taka}tk**.")

    else:
        await ctx.send("❌ Please include a valid currency format like `taka`, `tk`, `bdt`, `robux`, `rbx`, `r$`")

@bot.command(aliases=["commands", "cmds"])
async def help(ctx):
    if is_restricted(ctx):
        response = await ctx.send("❌ This command cannot be used in this channel.")
        await asyncio.sleep(5)
        await ctx.message.delete()
        await response.delete()
        return

    embed = discord.Embed(
        title="📜 Available Commands",
        description="Here's a list of commands you can use:",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="💱 `!convert <amount><currency>`",
        value="Convert between **Taka and Robux**.\nExamples: • `!convert 199tk` • `!convert 450 robux`",
        inline=False
    )

    embed.add_field(
        name="🧾 `!price`",
        value="Shows the current **Robux price chart**.",
        inline=False
    )

    embed.add_field(
        name="🤝 `!groups`",
        value="Lists the **Roblox groups** you must join to receive Robux.",
        inline=False
    )

    embed.add_field(
        name="⏰ `!remind`",
        value="Sets a **15-day reminder** after you join the required groups to become eligible for Robux.",
        inline=False
    )

    embed.set_footer(text="Note: Some commands are restricted to specific channels or roles.")
    await ctx.send(embed=embed)

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

bot.run(os.environ['DISCORD_TOKEN'])
