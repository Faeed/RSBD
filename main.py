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


@bot.command()
async def remind(ctx, roblox_username: str = None, mention: discord.Member = None):
    with open("reminders.json", "r") as f:
        reminders = json.load(f)

    author_id = str(ctx.author.id)
    allowed_role = 1334531528914370672
    log_channel = bot.get_channel(1372451862053261422)

    # 🔹 Show reminder list if no username is provided
    if roblox_username is None:
        target = mention or ctx.author
        # Restrict access if trying to check others
        if target != ctx.author and not any(role.id == allowed_role for role in ctx.author.roles):
            await ctx.send("❌ You don't have permission to view reminders for others.")
            return

        user_reminders = [v["roblox_username"] for v in reminders.values() if v["discord_id"] == str(target.id)]

        if not user_reminders:
            await ctx.send(f"📭 No active reminders found for {target.mention}.")
        else:
            formatted = "\n".join(f"- `{name}`" for name in user_reminders)
            embed = discord.Embed(
                title=f"🔔 Active Reminders for {target.display_name}",
                description=formatted,
                color=discord.Color.blurple()
            )
            await ctx.send(embed=embed)
        return

    # Fallback to the command sender if no mention is used
    if mention is None:
        mention = ctx.author
    else:
        if not any(role.id == allowed_role for role in ctx.author.roles):
            await ctx.send("❌ You don't have permission to set reminders for others.")
            return

    discord_id = str(mention.id)
    roblox_username = roblox_username.strip()

    # Check if this user already has 2 reminders
    count = sum(1 for v in reminders.values() if v["discord_id"] == discord_id)
    if count >= 2:
        await ctx.send("⚠️ You already have 2 active reminders.")
        return

    try:
        user = await roblox.get_user_by_username(roblox_username)
        user_id = str(user.id)
        proper_username = user.name
    except:
        await ctx.send("❌ Could not find that Roblox user.")
        return

    # Check payout status
    async with aiohttp.ClientSession() as session:
        headers = {"Cookie": f".ROBLOSECURITY={os.environ['ROBLOX_TOKEN']}"}
        payout_url = f"https://economy.roblox.com/v1/groups/{GROUP_ID}/users-payout-eligibility?userIds={user_id}"
        async with session.get(payout_url, headers=headers) as resp:
            data = await resp.json()
            status = data["usersGroupPayoutEligibility"].get(user_id, "Unknown")

    if status == "NotInGroup":
        await ctx.send(f"❌ **{proper_username}** is not in the group and can't be added.")
        return

    if status == "Eligible":
        await ctx.send(f"✅ **{proper_username}** is already eligible to purchase! Head to the store.")
        return

    if status != "PayoutRestricted":
        await ctx.send("❓ Could not determine user status.")
        return

    # Already reminded?
    if user_id in reminders:
        await ctx.send("⚠️ A reminder already exists for this Roblox user.")
        return

    # Save reminder
    now = datetime.utcnow()
    reminders[user_id] = {
        "roblox_username": proper_username,
        "discord_id": discord_id,
        "timestamp": now.isoformat()
    }

    with open("reminders.json", "w") as f:
        json.dump(reminders, f, indent=2)

    await ctx.send(f"📌 Reminder set! {mention.mention} will be notified when **{proper_username}** becomes eligible. You can ask a support to check logs if you need information.")

    # ✅ Send log embed
    log_embed = discord.Embed(
        title="📌 Reminder Created",
        description=f"Reminder set for **{proper_username}** (`{user_id}`)",
        color=discord.Color.blurple()
    )
    log_embed.add_field(name="Set By", value=f"{ctx.author.mention}", inline=True)
    log_embed.add_field(name="For", value=f"{mention.mention}", inline=True)
    log_embed.add_field(name="Time", value=f"<t:{int(now.timestamp())}>", inline=False)
    await log_channel.send(embed=log_embed)

@tasks.loop(hours=6)
async def check_reminders():
    channel = bot.get_channel(1372451862053261422)  # Log channel

    with open("reminders.json", "r") as f:
        reminders = json.load(f)

    updated = False
    user_ids = list(reminders.keys())

    for user_id in user_ids:
        info = reminders[user_id]
        discord_id = int(info["discord_id"])
        username = info["roblox_username"]
        thumbnail_url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png&isCircular=false"

        # Wait 3 minutes between each
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
        description = f"**{username}** is still not eligible for payout."

        if status == "Eligible":
            # DM the user
            embed = discord.Embed(
                title="✅ Payout Eligible!",
                description=f"Your Roblox account **{username}** is now eligible to purchase Robux in RSBD!\n[Click here to buy now](https://discord.com/channels/1334140159012241410/1334535165187326053)",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=thumbnail_url)

            try:
                await user.send(embed=embed)
            except:
                await channel.send(f"⚠️ Couldn't DM {user.mention} for **{username}**.")

            # Log
            color = discord.Color.green()
            title = "✅ Notified"
            description = f"**{username}** is now eligible and was notified via DM."

            # Remove from JSON
            del reminders[user_id]
            updated = True

        elif status == "NotInGroup":
            description = f"**{username}** left the group. Removed reminder."
            del reminders[user_id]
            updated = True

        log_embed = discord.Embed(title=title, description=description, color=color)
        await channel.send(embed=log_embed)

    if updated:
        with open("reminders.json", "w") as f:
            json.dump(reminders, f, indent=2)


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
    load_reminders()
    if not save_reminder_task.is_running():
        save_reminder_task.start()
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
