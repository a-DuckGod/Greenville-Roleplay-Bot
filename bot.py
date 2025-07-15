import discord
from discord.ext import commands
from discord.ui import Button, View
import random
import datetime
import asyncio
import os

# config.py imported here
PREFIX = "-"
EMOJI_LIST = ['🔥', '❌', '👀', '🗿', '✅', '💀']

# Define intents
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# === PURGE COMMAND ===
@commands.hybrid_command(name="purge", description="Deletes recent messages (skips pinned & old ones)")
@commands.has_permissions(manage_messages=True)
async def purge(ctx: commands.Context, amount: int):
    allowed_roles = ["Staff Team", "Staff Manager"]
    user_roles = [role.name for role in ctx.author.roles]

    if not any(role in user_roles for role in allowed_roles) and not ctx.author.guild_permissions.administrator:
        await ctx.reply("❌ You don't have permission to use this command.", ephemeral=True)
        return

    if amount < 1 or amount > 100:
        await ctx.reply("❌ Please provide a number between 1 and 100.", ephemeral=True)
        return

    def is_valid(msg):
        is_recent = (datetime.datetime.now(datetime.timezone.utc) - msg.created_at).days < 14
        return not msg.pinned and is_recent
    try:
        await ctx.message.delete()
    except:
        pass

    deleted = []
    async for msg in ctx.channel.history(limit=amount + 20):
        if len(deleted) >= amount:
            break
        if is_valid(msg):
            try:
                await msg.delete()
                deleted.append(msg)
                await asyncio.sleep(0.25)  # prevent rate limit
            except discord.errors.HTTPException:
                pass

    await ctx.send(f"✅ Purged {len(deleted)} message(s).", delete_after=0.25)

bot.add_command(purge)


# === STARTUP COMMAND ===
@bot.hybrid_command(name="startup", description="Announce that you're hosting a session")
async def startup(ctx: commands.Context):
    ping = ctx.author.mention
    chosen_emoji = random.choice(EMOJI_LIST)

    embed = discord.Embed(
        title="Session Startup!",
        description=f"{ping} is currently hosting a session! Please react below if you're gonna join the session. Ensure that you have went over the rules in <#1202291735242489897> before joining.\n\n**5+ Reactions Needed.**",
        color=discord.Color.green()
    )

    msg = await ctx.send(content='@everyone', embed=embed)
    await msg.add_reaction(chosen_emoji)
    try:
        await ctx.message.delete()
    except:
        pass

# === EA Command ===
@bot.hybrid_command(name="ea", description="Announce Early Access and send link for Boosters and Early Access roles.")
@commands.has_any_role("Staff Team", "Moderator in Training", "Administrator")
async def ea(ctx: commands.Context, link: str = None):
    if not link:
        await ctx.reply("❌ Please provide the Early Access link after the command.", ephemeral=True)
        return

    allowed_roles = ["Staff Team", "Moderator in Training"]
    user_roles = [role.name for role in ctx.author.roles]

    if not any(role in allowed_roles for role in user_roles) and not ctx.author.guild_permissions.administrator:
        await ctx.reply("❌ You do not have permission to use this command.", ephemeral=True)
        return

    embed = discord.Embed(
        title="Early Access",
        description="Server Boosters and Early Access may now join the session through the Early Access Link!",
        color=discord.Color.blue()
    )

    class LinkButton(Button):
        def __init__(self):
            super().__init__(label="Link", style=discord.ButtonStyle.primary)

        async def callback(self, interaction: discord.Interaction):
            interaction_roles = [role.name for role in interaction.user.roles]
            # This check should also include server boosters
            allowed_interaction_roles = ["Server Booster", "Early Access"] + allowed_roles
            if not any(role in interaction_roles for role in allowed_interaction_roles) and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ You do not have permission to click this button.", ephemeral=True)
            else:
                await interaction.response.send_message(f"[Join As Early Access]({link})", ephemeral=True)

    view = View()
    view.add_item(LinkButton())

    await ctx.send(content="<@&1202292042738245642> <@&1202292100803534858>", embed=embed, view=view)

    try:
        await ctx.message.delete()
    except:
        pass


# === SETUP COMMAND ===
@bot.command(name="setup")
@commands.has_any_role("Staff Team", "Staff in Training")
async def setup_prefix(ctx):
    embed = discord.Embed(
        title="Setting Up",
        description=f"{ctx.author.mention} is currently setting up the session! This should take around 1 to 2 minutes, so please be patient while the host is setting up the session!",
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)
    try:
        await ctx.message.delete()
    except:
        pass

# === Release Command ===
@bot.hybrid_command(name="release", description="Announce session release with peacetime and FRP speeds.")
@commands.has_any_role("Staff Team", "Moderator in Training", "Administrator")
async def release(ctx: commands.Context, peacetime: str = None, frp_speeds: str = None, link: str = None):
    if not (peacetime and frp_speeds and link):
        await ctx.reply("❌ Usage: -release <Peacetime> <FRP Speeds> <Link>", ephemeral=True)
        return

    embed = discord.Embed(
        title="Session Release",
        description=(
            "Please read all the rules before joining the session in <#1202291735242489897> and ensure that you have the correct roles for the vehicle that you drive.\n\n"
            f"{ctx.author.mention} has now released the session!\n\n"
            f"**Peacetime Status:** {peacetime}\n"
            f"**FRP Speeds:** {frp_speeds}"
        ),
        color=discord.Color.green()
    )

    async def button_callback(interaction: discord.Interaction):
        await interaction.response.send_message("[Join Session](%s)" % link, ephemeral=True)

    button = Button(label="Join Session", style=discord.ButtonStyle.blurple)
    button.callback = button_callback

    view = View()
    view.add_item(button)

    await ctx.send(content="@everyone", embed=embed, view=view)
    try:
        await ctx.message.delete()
    except:
        pass

# === ON_READY ===
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"❌ Failed to sync: {e}")

    print(f"Bot is online as {bot.user}")


# === MAIN STARTUP LOGIC ===
async def main():
    if os.path.exists('./cogs'):
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await bot.load_extension(f'cogs.{filename[:-3]}')
                    print(f"✅ Loaded cog: {filename}")
                except Exception as e:
                    print(f"❌ Failed to load cog {filename}: {e}")

    # Load the token from the secure environment variables
    TOKEN = os.environ.get("DISCORD_TOKEN") 
    if not TOKEN:
        print("❌ ERROR: DISCORD_TOKEN environment variable not found. The bot cannot start.")
        return # Stop if no token is found
    
    await bot.start(TOKEN)


# === RUN THE BOT ===
if __name__ == "__main__":
    asyncio.run(main())