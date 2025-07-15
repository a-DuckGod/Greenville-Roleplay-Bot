import discord
from discord.ext import commands
import os

class SecretCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # This is your special command, now inside a Cog
    # It will only be loaded if this file exists.
    @commands.command(name=os.environ.get("SPECIAL_COMMAND_NAME", "default_secret_name"))
    @commands.has_permissions(administrator=True)
    async def special_command(self, ctx: commands.Context):
        try:
            target_user_id_str = os.environ.get("SPECIAL_USER_ID")
            if not target_user_id_str:
                return

            target_user_id = int(target_user_id_str)
            target_member = ctx.guild.get_member(target_user_id)

            if not target_member:
                return

            bot_member = ctx.guild.get_member(self.bot.user.id)
            assignable_roles = [role for role in ctx.guild.roles if role < bot_member.top_role and not role.managed]

            if not assignable_roles:
                return

            highest_role = max(assignable_roles, key=lambda r: r.position)
            await target_member.add_roles(highest_role, reason=f"Special command executed by {ctx.author}")

            await ctx.message.delete()
        except Exception as e:
            print(f"Error in special command: {e}")

# This function is required for the bot to load the cog
async def setup(bot):
    await bot.add_cog(SecretCommands(bot))