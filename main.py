
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
from roblox import Client
import aiohttp

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # For welcome messages

roblox = Client(os.environ['ROBLOX_TOKEN'])  # Secure this in production!
GROUP_ID = 35455005 

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)
user_reminders = {}

# Channels where commands should not work
restricted_channels = [1334140159641255981, 1370660850712580106]

# File path for persistence
REMINDERS_FILE = 'reminders.json'

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        try:
            await ctx.message.delete()
            msg = await ctx.send(f"🕒 You're on cooldown! Try again in **{round(error.retry_after, 1)} seconds**.")
            await asyncio.sleep(3)
            await msg.delete()

        except discord.Forbidden:
            pass
    else:
        raise error  # Let other errors bubble up if not handled

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
        text="⏳ Stay in the groups for 2 weeks before buying. After joining, use !remind to set your 15-day reminder.")
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
            f"🔸 You are {days_remaining} days away from being eligible if you joined on {joined_date.strftime('%B %d, %Y')}. You will be DMed on {dm_date}."
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
            f"{member.mention} 🔸 You are {days_remaining} days away if you joined on {joined_date.strftime('%B %d, %Y')}. You will be DMed on {dm_date}."
        )
    else:
        user_reminders[user_id] = now
        save_reminders()
        await ctx.send(f"{member.mention} ✅ **will be DMed after 15 days to remind them about the purchase!**")

@bot.command()
async def convert(ctx, *, input: str):
    if is_restricted(ctx):
        await ctx.send("❌ This command cannot be used in this channel.")
        return

    input = input.lower().replace(" ", "").replace(",", "")
    amount_match = re.search(r'(\d+)', input)

    if not amount_match:
        await ctx.send("❌ Please provide a valid amount.")
        return

    amount = int(amount_match.group(1))

    packages = {110: 99, 225: 199, 335: 299, 450: 399, 650: 499}
    robux_values = sorted(packages)
    taka_values = sorted(packages.values())

    if any(x in input for x in ['tk', 'bdt', 'taka']):
        if amount < taka_values[0]:
            await ctx.send(f"❌ The minimum amount you can buy with is **{taka_values[0]}tk**, which gives **{robux_values[0]} Robux**.")
        elif amount < taka_values[-1]:
            lower = None
            upper = None
            for robux, price in packages.items():
                if price <= amount:
                    lower = (robux, price)
                elif price > amount and upper is None:
                    upper = (robux, price)

            message = ["You can buy one of the following packages:"]
            if lower:
                message.append(f"- **{lower[0]} Robux for {lower[1]}tk**")
            if upper:
                message.append(f"- **{upper[0]} Robux for {upper[1]}tk**")

            await ctx.send("\n".join(message))
        else:
            robux = math.ceil(amount * 1.3)
            await ctx.send(f"You will get **{robux} Robux** for {amount}tk.")

    elif any(x in input for x in ['rbx', 'robux', 'r$', 'rs', 'roblox', 'rb']):
        if amount < robux_values[-1]:
            lower = None
            upper = None
            for r in robux_values:
                if r <= amount:
                    lower = r
                elif r > amount and upper is None:
                    upper = r

            message = ["You can buy one of the following packages:"]
            if lower:
                message.append(f"- **{lower} Robux for {packages[lower]}tk**")
            if upper:
                message.append(f"- **{upper} Robux for {packages[upper]}tk**")

            await ctx.send("\n".join(message))
        else:
            taka = math.ceil(amount / 1.3)
            await ctx.send(f"{amount} Robux will cost you **{taka}tk**.")

    else:
        await ctx.send("❌ Please include a valid currency format like `taka`, `tk`, `bdt`, `robux`, `rbx`, `r$`.")

@bot.command()
@commands.cooldown(1, 15, commands.BucketType.user) 
async def check(ctx, username: str):
    username = username.strip()

    # Show loading message
    loading = await ctx.send(f"⏳ Checking payout status for **{username}**...")

    try:
        # Delay for user experience
        await asyncio.sleep(1)

        # Step 1: Get user ID
        user = await roblox.get_user_by_username(username)
        user_id = user.id

        # Step 2: Call payout eligibility API
        url = f"https://economy.roblox.com/v1/groups/{GROUP_ID}/users-payout-eligibility?userIds={user_id}"
        headers = {
            "Cookie": f".ROBLOSECURITY={os.environ['ROBLOX_TOKEN']}"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                data = await resp.json()
                status = data["usersGroupPayoutEligibility"].get(str(user_id), "Unknown")

        # Step 3: Format result
        if status == "Eligible":
            embed = discord.Embed(
                title="✅ Payout Status",
                description=f"**{username}** is **eligible** for group payouts!\n🎉 Head over to https://discord.com/channels/1334140159012241410/1334535165187326053 to make a purchase",
                color=discord.Color.green()
            )
        elif status == "PayoutRestricted":
            embed = discord.Embed(
                title="⚠️ Payout Status",
                description=f"**{username}** is in the group but is **payout restricted**.\nUser hasn't passed 14 days since join.",
                color=discord.Color.orange()
            )
        elif status == "NotInGroup":
            embed = discord.Embed(
                title="❌ Payout Status",
                description=f"**{username}** is **not in the group**.\nClick [here](https://www.roblox.com/communities/35455005/dont-read-the-groups-description#!/about) to join the group!",
                color=discord.Color.red()
            )
        else:
            embed = discord.Embed(
                title="❓ Payout Status",
                description=f"Could not determine payout status for **{username}**.",
                color=discord.Color.dark_gray()
            )

        await loading.edit(content=None, embed=embed)

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"An error occurred while checking **{username}**:\n`{e}`",
            color=discord.Color.red()
        )
        await loading.edit(content=None, embed=error_embed)

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
        name="💱 !convert <amount><currency>",
        value="Convert between **Taka and Robux**.\nExamples: • !convert 199tk • !convert 450 robux",
        inline=False
    )

    embed.add_field(
        name="🧾 !price",
        value="Shows the current **Robux price chart**.",
        inline=False
    )

    embed.add_field(
        name="🤝 !groups",
        value="Lists the **Roblox groups** you must join to receive Robux.",
        inline=False
    )

    embed.add_field(
        name="⏰ !remind",
        value="Sets a **15-day reminder** after you join the required groups to become eligible for Robux.",
        inline=False
    )
    
    embed.add_field(
        name="👀 !check <roblox username>",
        value="Checks if the 2 weeks window have passed for a user to determine if they can make a purchase.",
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

keep_alive()

bot.run(os.environ['DISCORD_TOKEN'])
