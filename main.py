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

REMINDER_CHANNEL_ID = 1372592046048542760  # "Database" channel
LOG_CHANNEL_ID = 1372451862053261422       # Log channel
ALLOWED_ROLE_ID = 1334531528914370672      # Admin/Manager role

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Channels where commands should not work
restricted_channels = [1334140159641255981, 1370660850712580106]

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

async def fetch_reminders_for_discord_id(discord_id: str):
    channel = bot.get_channel(REMINDER_CHANNEL_ID)
    messages = await channel.history(limit=100).flatten()
    reminders = []
    for msg in messages:
        if msg.content.startswith("REMINDER_DATA:"):
            try:
                data = json.loads(msg.content.split("REMINDER_DATA:")[1])
                if data.get("discord_id") == discord_id:
                    reminders.append(data)
            except:
                continue
    return reminders

@bot.command()
async def remind(ctx, roblox_username: str = None, mention: discord.Member = None):
    reminder_channel = bot.get_channel(REMINDER_CHANNEL_ID)
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    author = ctx.author
    author_id = str(author.id)

    def has_allowed_role(member):
        return any(role.id == ALLOWED_ROLE_ID for role in member.roles)

    # No username = list own reminders
    if roblox_username is None:
        reminders = await fetch_reminders_for_discord_id(author_id)
        if not reminders:
            await ctx.send("📭 You have **no active reminders.**")
            return
        embed = discord.Embed(title="🔔 Your Active Reminders", color=discord.Color.blurple())
        for r in reminders:
            embed.add_field(name=r["roblox_username"], value=f"Added: <t:{r['timestamp']}:R>", inline=False)
        await ctx.send(embed=embed)
        return

    # Admin-only "list" feature
    if roblox_username.lower() == "list" and mention:
        if not has_allowed_role(author):
            await ctx.send("❌ You don't have permission to use this.")
            return
        target_id = str(mention.id)
        reminders = await fetch_reminders_for_discord_id(target_id)
        if not reminders:
            await ctx.send(f"📭 No reminders for {mention.mention}.")
            return
        embed = discord.Embed(title=f"📋 Reminders for {mention.display_name}", color=discord.Color.blurple())
        for r in reminders:
            embed.add_field(name=r["roblox_username"], value=f"Added: <t:{r['timestamp']}:R>", inline=False)
        await ctx.send(embed=embed)
        return

    # Fallback to sender if no mention
    if mention is None:
        mention = ctx.author

    discord_id = str(mention.id)

    # Check Roblox username
    try:
        roblox_user = await roblox.get_user_by_username(roblox_username)
        roblox_id = str(roblox_user.id)
        roblox_username = roblox_user.name
    except:
        await ctx.send("❌ Could not find that Roblox user. Please provide correct username.")
        return

    # Check payout eligibility
    async with aiohttp.ClientSession() as session:
        headers = {"Cookie": f".ROBLOSECURITY={os.environ['ROBLOX_TOKEN']}"}
        url = f"https://economy.roblox.com/v1/groups/{GROUP_ID}/users-payout-eligibility?userIds={roblox_id}"
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            status = data["usersGroupPayoutEligibility"].get(roblox_id, "Unknown")

    if status == "NotInGroup":
        await ctx.send(f"❌ **{roblox_username}** is **not in the group**, so a reminder cannot be added.")
        return
    if status == "Eligible":
        await ctx.send(f"✅ **{roblox_username}** is already **eligible**! Go & make a purchase from <1334535165187326053>")
        return
    if status != "PayoutRestricted":
        await ctx.send("❓ Unable to determine payout status.")
        return

    # Check existing reminders for this Discord user
    existing = await fetch_reminders_for_discord_id(discord_id)
    if not has_allowed_role(ctx.author) and len(existing) >= 2:
        await ctx.send("⚠️ You already have 2 active reminders.")
        return
    if any(r["roblox_id"] == roblox_id for r in existing) and not has_allowed_role(ctx.author):
        await ctx.send("⚠️ You already set a reminder for this Roblox user.")
        return

    # Add reminder as message
    timestamp = int(datetime.utcnow().timestamp())
    payload = {
        "roblox_id": roblox_id,
        "roblox_username": roblox_username,
        "discord_id": discord_id,
        "timestamp": timestamp
    }
    await reminder_channel.send(f"REMINDER_DATA:{json.dumps(payload)}")

    await ctx.send(f"📌 Reminder set! {mention.mention} will be notified when **{roblox_username}** is eligible.")

    # Log
    embed = discord.Embed(
        title="📌 Reminder Added",
        description=f"{mention.mention} added a reminder for **{roblox_username}**",
        color=discord.Color.orange()
    )
    await log_channel.send(embed=embed)


@tasks.loop(hours=6)
async def check_reminders():
    REMINDER_PREFIX = "REMINDER_DATA:"

    if not REMINDER_CHANNEL_ID or not LOG_CHANNEL_ID:
        print("⚠️ One of the channels could not be fetched.")
        return

    messages = await REMINDER_CHANNEL_ID.history(limit=100).flatten()
    reminders = []

    for msg in messages:
        if msg.content.startswith(REMINDER_PREFIX):
            try:
                data = json.loads(msg.content[len(REMINDER_PREFIX):])
                reminders.append((data, msg))
            except:
                continue

    for reminder, msg in reminders:
        user_id = reminder["roblox_id"]
        discord_id = int(reminder["discord_id"])
        username = reminder["roblox_username"]
        thumbnail_url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png&isCircular=false"

        await asyncio.sleep(180)

        async with aiohttp.ClientSession() as session:
            headers = {"Cookie": f".ROBLOSECURITY={os.environ['ROBLOX_TOKEN']}"}
            payout_url = f"https://economy.roblox.com/v1/groups/{GROUP_ID}/users-payout-eligibility?userIds={user_id}"
            async with session.get(payout_url, headers=headers) as resp:
                data = await resp.json()
                status = data["usersGroupPayoutEligibility"].get(user_id, "Unknown")

        user = bot.get_user(discord_id)
        color = discord.Color.red()
        title = "❌ Still Not Eligible"
        description = f"**{username}** ({discord_id}) is still not eligible for payout."

        if status == "Eligible":
            embed = discord.Embed(
                title="✅ Payout Eligible!",
                description=f"Your Roblox account **{username}** is now eligible to purchase Robux in RSBD!\n[Click here to buy now](https://discord.com/channels/1334140159012241410/1334535165187326053)",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=thumbnail_url)

            try:
                await user.send(embed=embed)
            except:
                await LOG_CHANNEL_ID.send(f"⚠️ Couldn't DM <@{discord_id}> for **{username}**.")

            color = discord.Color.green()
            title = "✅ Notified"
            description = f"**{username}** ({discord_id}) is now eligible and was notified via DM."

            await msg.delete()

        elif status == "NotInGroup":
            description = f"**{username}** left the group. Removed reminder."
            await msg.delete()

        log_embed = discord.Embed(title=title, description=description, color=color)
        await LOG_CHANNEL_ID.send(embed=log_embed)

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
@commands.cooldown(1, 10, commands.BucketType.user)
async def check(ctx, username: str):
    username = username.strip()
    loading = await ctx.send(f"⏳ Checking payout status for **{username}**...")

    try:
        await asyncio.sleep(1)

        user = await roblox.get_user_by_username(username)
        user_id = user.id
        proper_username = user.name
        profile_link = f"https://www.roblox.com/users/{user_id}/profile"
        markdown_user = f"[{proper_username}]({profile_link})"

        thumbnail_url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png&isCircular=false"

        async with aiohttp.ClientSession() as session:
            # Step 3: Get payout eligibility
            payout_url = f"https://economy.roblox.com/v1/groups/{GROUP_ID}/users-payout-eligibility?userIds={user_id}"
            headers = {
                "Cookie": f".ROBLOSECURITY={os.environ['ROBLOX_TOKEN']}"
            }
            async with session.get(payout_url, headers=headers) as resp:
                data = await resp.json()
                status = data["usersGroupPayoutEligibility"].get(str(user_id), "Unknown")

            # Step 4: Get avatar image URL
            async with session.get(thumbnail_url) as thumb_resp:
                thumb_data = await thumb_resp.json()
                user_avatar_url = thumb_data["data"][0]["imageUrl"]

        # Step 5: Create response embed
        if status == "Eligible":
            embed = discord.Embed(
                title="✅ Payout Status",
                description=f"**{markdown_user}** is **eligible** for group payouts!\n🎉 Head over to https://discord.com/channels/1334140159012241410/1334535165187326053 to make a purchase",
                color=discord.Color.green()
            )
        elif status == "PayoutRestricted":
            embed = discord.Embed(
                title="⚠️ Payout Status",
                description=f"**{markdown_user}** is in the group but is **payout restricted**.\nUser hasn't passed 14 days since join.",
                color=discord.Color.orange()
            )
        elif status == "NotInGroup":
            embed = discord.Embed(
                title="❌ Payout Status",
                description=f"**{markdown_user}** is **not in the group**.\nClick [here](https://www.roblox.com/communities/35455005/dont-read-the-groups-description#!/about) to join the group!",
                color=discord.Color.red()
            )
        else:
            embed = discord.Embed(
                title="❓ Payout Status",
                description=f"Could not determine payout status for **{markdown_user}**.",
                color=discord.Color.dark_gray()
            )

        embed.set_thumbnail(url=user_avatar_url)
        await loading.edit(content=None, embed=embed)

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"An error occurred while checking **{username.title()}**:\n`{e}`",
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
        name="⏰ !remind <roblox username>",
        value="If the user is in group but not eligible, it will add a reminder and the bot will check every few hours to notify you in DMs when the user is eligible for a payout. Leave username empty to see your active reminders.",
        inline=False
    )
    
    embed.add_field(
        name="👀 !check <roblox username>",
        value="Checks if the 2 weeks window have passed for a user to determine if they can make a purchase.",
        inline=False
    )

    embed.set_footer(text="Note: Some commands are restricted to specific channels or roles.")
    await ctx.send(embed=embed)

@bot.event
async def on_ready():

    if not check_reminders.is_running():
        check_reminders.start()
        
    print(f'✅ Logged in as {bot.user}')

def is_restricted(ctx):
    return ctx.channel.id in restricted_channels

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
