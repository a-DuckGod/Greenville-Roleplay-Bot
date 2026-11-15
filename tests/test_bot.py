from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import os
import pytest
import discord

import bot as bot_module
from cogs.config_cog import ConfigCog, build_config_embed
from cogs.general import GeneralCog
from cogs.moderation import ModerationCog
from cogs.session import EarlyAccessLinkView, ReleaseLinkView, SessionCog
from database import Database, GuildConfig
import utils


def make_role(role_id: int, name: str, *, is_default: bool = False):
    role = MagicMock(spec=discord.Role)
    role.id = role_id
    role.name = name
    role.mention = f"<@&{role_id}>"
    role.is_default = MagicMock(return_value=is_default)
    return role


def make_member(
    user_id: int,
    roles: list | None = None,
    *,
    administrator: bool = False,
    manage_guild: bool = False,
    manage_messages: bool = False,
    display_name: str = "TestUser",
):
    member = MagicMock(spec=discord.Member)
    member.id = user_id
    member.mention = f"<@{user_id}>"
    member.display_name = display_name
    member.roles = roles or []
    perms = discord.Permissions(
        administrator=administrator,
        manage_guild=manage_guild,
        manage_messages=manage_messages,
    )
    member.guild_permissions = perms
    return member


def make_guild(
    guild_id: int,
    *,
    name: str = "Test Server",
    channels: dict[int, MagicMock] | None = None,
    roles: dict[int, MagicMock] | None = None,
    premium_role=None,
):
    guild = MagicMock(spec=discord.Guild)
    guild.id = guild_id
    guild.name = name
    channels = channels or {}
    roles = roles or {}
    guild.get_channel = MagicMock(side_effect=lambda cid: channels.get(cid))
    guild.get_role = MagicMock(side_effect=lambda rid: roles.get(rid))
    guild.premium_subscriber_role = premium_role
    return guild


class TestDatabase:
    def test_multi_server_isolation(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        try:
            cfg1 = db.get_guild_config(1001)
            cfg2 = db.get_guild_config(1002)
            assert cfg1.prefix == "-"
            assert cfg2.prefix == "-"

            db.update_guild_config(
                1001,
                prefix="!",
                rules_channel_id=555,
                staff_role_ids=[10, 20],
                required_reactions=8,
            )

            # Re-instantiate DB from disk to verify persistence
            db.close()
            db2 = Database(str(tmp_path / "test.db"))
            loaded1 = db2.get_guild_config(1001)
            loaded2 = db2.get_guild_config(1002)

            assert loaded1.prefix == "!"
            assert loaded1.rules_channel_id == 555
            assert loaded1.staff_role_ids == [10, 20]
            assert loaded1.required_reactions == 8

            assert loaded2.prefix == "-"
            assert loaded2.rules_channel_id is None
            assert loaded2.staff_role_ids == []

            reset1 = db2.reset_guild_config(1001)
            assert reset1.prefix == "-"
            assert reset1.rules_channel_id is None
            db2.close()
        finally:
            try:
                db.close()
            except Exception:
                pass

    def test_session_links_persistence(self, tmp_path):
        db = Database(str(tmp_path / "links.db"))
        db.save_session_link(999, 1001, "ea", "https://www.roblox.com/share?code=abc", 42)
        rec = db.get_session_link(999)
        assert rec is not None
        assert rec["url"] == "https://www.roblox.com/share?code=abc"
        assert rec["link_type"] == "ea"
        assert db.get_session_link(12345) is None
        db.close()


class TestUtils:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("https://www.roblox.com/share?code=123", "https://www.roblox.com/share?code=123"),
            (" <http://example.com/path> ", "http://example.com/path"),
            ("not-a-url", None),
            ("javascript:alert(1)", None),
            ("https://example.com/bad)markdown", None),
            ("https://example.com/has space", None),
            ("", None),
        ],
    )
    def test_validate_url(self, raw, expected):
        assert utils.validate_url(raw) == expected

    def test_staff_permissions(self):
        staff_role = make_role(10, "RP Host")
        other_role = make_role(20, "Civilian")
        default_staff = make_role(30, "Staff Team")

        # Unconfigured server falls back to permissions or standard role names
        cfg_default = GuildConfig(guild_id=1)
        assert utils.is_staff_member(make_member(1, manage_messages=True), cfg_default)
        assert utils.is_staff_member(make_member(2, roles=[default_staff]), cfg_default)
        assert not utils.is_staff_member(make_member(3, roles=[other_role]), cfg_default)

        # Configured server enforces configured staff_role_ids (plus mod/admin perms)
        cfg_custom = GuildConfig(guild_id=1, staff_role_ids=[10])
        assert utils.is_staff_member(make_member(4, roles=[staff_role]), cfg_custom)
        assert not utils.is_staff_member(make_member(5, roles=[default_staff]), cfg_custom)

    def test_ea_eligibility(self):
        ea_role = make_role(100, "VIP Early Access")
        native_booster = make_role(200, "Nitro Booster")
        custom_booster = make_role(201, "Server Booster")
        civilian = make_role(300, "Member")

        guild = make_guild(1, premium_role=native_booster)
        cfg = GuildConfig(guild_id=1, ea_role_ids=[100], booster_role_id=201)

        assert utils.is_ea_eligible(make_member(1, roles=[ea_role]), guild, cfg)
        assert utils.is_ea_eligible(make_member(2, roles=[native_booster]), guild, cfg)
        assert utils.is_ea_eligible(make_member(3, roles=[custom_booster]), guild, cfg)
        assert utils.is_ea_eligible(make_member(4, manage_messages=True), guild, cfg)
        assert not utils.is_ea_eligible(make_member(5, roles=[civilian]), guild, cfg)


class TestBotAndCommands:
    @pytest.mark.asyncio
    async def test_cogs_and_prefix_per_guild(self, tmp_path):
        bot = bot_module.GreenvilleBot(db_path=str(tmp_path / "bot.db"))
        bot._connection.user = SimpleNamespace(id=777777, name="Greenville Roleplay Bot", mention="<@777777>")

        await bot.load_extension("cogs.session")
        await bot.load_extension("cogs.moderation")
        await bot.load_extension("cogs.config_cog")
        await bot.load_extension("cogs.general")

        bot.add_view(EarlyAccessLinkView())
        bot.add_view(ReleaseLinkView())

        prefix_names = {cmd.name for cmd in bot.commands}
        assert {"startup", "setup", "ea", "release", "over", "purge", "config", "help", "invite", "ping"}.issubset(
            prefix_names
        )

        slash_names = {cmd.name for cmd in bot.tree.get_commands()}
        assert {"startup", "setup", "ea", "release", "over", "purge", "config", "help", "invite", "ping"}.issubset(
            slash_names
        )

        # Verify dynamic prefix per guild
        bot.db.update_guild_config(111, prefix="!")
        msg1 = SimpleNamespace(guild=SimpleNamespace(id=111))
        msg2 = SimpleNamespace(guild=SimpleNamespace(id=222))

        prefixes1 = bot_module.get_prefix(bot, msg1)
        prefixes2 = bot_module.get_prefix(bot, msg2)
        assert "!" in prefixes1
        assert "-" in prefixes2

        await bot.close()

    @pytest.mark.asyncio
    async def test_startup_and_release_multi_server(self, tmp_path):
        bot = bot_module.GreenvilleBot(db_path=str(tmp_path / "sess.db"))
        cog = SessionCog(bot)

        rules_ch = MagicMock(spec=discord.TextChannel)
        rules_ch.id = 500
        rules_ch.mention = "<#500>"

        announce_ch = MagicMock(spec=discord.TextChannel)
        announce_ch.id = 501
        announce_ch.mention = "<#501>"
        sent_msg = MagicMock()
        sent_msg.id = 8888
        sent_msg.add_reaction = AsyncMock()
        announce_ch.send = AsyncMock(return_value=sent_msg)

        guild = make_guild(42, channels={500: rules_ch, 501: announce_ch})
        bot.db.update_guild_config(
            42,
            rules_channel_id=500,
            session_channel_id=501,
            required_reactions=10,
            startup_ping="here",
        )

        ctx = MagicMock()
        ctx.guild = guild
        ctx.author = make_member(99, administrator=True, display_name="HostUser")
        ctx.channel = rules_ch
        ctx.interaction = None
        ctx.message = MagicMock()
        ctx.message.delete = AsyncMock()

        await cog.startup.callback(cog, ctx, None)

        announce_ch.send.assert_awaited_once()
        kwargs = announce_ch.send.call_args.kwargs
        assert kwargs["content"] == "@here"
        assert "<#500>" in kwargs["embed"].description
        assert "**10+ Reactions Needed.**" in kwargs["embed"].description
        sent_msg.add_reaction.assert_awaited_once()

        # Test release saves link to database
        await cog.release.callback(cog, ctx, "Normal", "75 MPH", "https://www.roblox.com/share?code=xyz")
        saved = bot.db.get_session_link(8888)
        assert saved is not None
        assert saved["link_type"] == "release"
        assert saved["url"] == "https://www.roblox.com/share?code=xyz"

        bot.db.close()

    @pytest.mark.asyncio
    async def test_ea_button_gatekeeping(self, tmp_path):
        bot = bot_module.GreenvilleBot(db_path=str(tmp_path / "ea.db"))
        bot._connection.user = SimpleNamespace(id=777777)
        ea_role = make_role(301, "Early Access")
        member_role = make_role(302, "Citizen")
        guild = make_guild(77, roles={301: ea_role, 302: member_role})

        bot.db.update_guild_config(77, ea_role_ids=[301])
        bot.db.save_session_link(5555, 77, "ea", "https://www.roblox.com/share?code=vip", 1)

        view = EarlyAccessLinkView()
        button = view.children[0]

        # Non-EA user gets denied
        bad_interaction = MagicMock(spec=discord.Interaction)
        bad_interaction.guild = guild
        bad_interaction.user = make_member(10, roles=[member_role])
        bad_interaction.message = SimpleNamespace(id=5555)
        bad_interaction.client = bot
        bad_interaction.response = MagicMock()
        bad_interaction.response.send_message = AsyncMock()

        await button.callback(bad_interaction)
        bad_interaction.response.send_message.assert_awaited_once()
        assert "❌" in bad_interaction.response.send_message.call_args.args[0]

        # EA user gets link ephemerally
        good_interaction = MagicMock(spec=discord.Interaction)
        good_interaction.guild = guild
        good_interaction.user = make_member(11, roles=[ea_role])
        good_interaction.message = SimpleNamespace(id=5555)
        good_interaction.client = bot
        good_interaction.response = MagicMock()
        good_interaction.response.send_message = AsyncMock()

        await button.callback(good_interaction)
        good_interaction.response.send_message.assert_awaited_once()
        assert "https://www.roblox.com/share?code=vip" in good_interaction.response.send_message.call_args.args[0]
        assert good_interaction.response.send_message.call_args.kwargs["ephemeral"] is True

        bot.db.close()

    def test_build_config_embed(self):
        rules_ch = MagicMock(spec=discord.TextChannel)
        rules_ch.id = 123
        rules_ch.mention = "<#123>"
        staff_role = make_role(456, "Staff")
        guild = make_guild(99, name="My GVRP", channels={123: rules_ch}, roles={456: staff_role})
        cfg = GuildConfig(guild_id=99, rules_channel_id=123, staff_role_ids=[456], prefix="?")

        embed = build_config_embed(guild, cfg)
        assert "My GVRP" in embed.title
        fields = {f.name: f.value for f in embed.fields}
        assert fields["Command Prefix"] == "`?`"
        assert fields["Rules Channel"] == "<#123>"
        assert "<@&456>" in fields["Staff / Host Roles"]

    def test_resolve_token(self, monkeypatch):
        monkeypatch.delenv("BOT_TOKEN", raising=False)
        monkeypatch.delenv("DISCORD_TOKEN", raising=False)
        monkeypatch.setattr(bot_module.config, "TOKEN", "YOUR_REAL_BOT_TOKEN")
        with pytest.raises(RuntimeError):
            bot_module.resolve_token()

        monkeypatch.setenv("BOT_TOKEN", "real-token-123")
        assert bot_module.resolve_token() == "real-token-123"

    @pytest.mark.asyncio
    async def test_purge_and_release_button_and_general(self, tmp_path):
        bot = bot_module.GreenvilleBot(db_path=str(tmp_path / "extra.db"))
        bot._connection.user = SimpleNamespace(id=777777, name="Greenville Roleplay Bot", mention="<@777777>")
        mod_cog = ModerationCog(bot)
        sess_cog = SessionCog(bot)
        cfg_cog = ConfigCog(bot)
        gen_cog = GeneralCog(bot)

        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 600
        channel.mention = "<#600>"
        channel.permissions_for = MagicMock(
            return_value=discord.Permissions(manage_messages=True, send_messages=True)
        )
        channel.purge = AsyncMock(return_value=[object(), object(), object()])
        sent_msg = MagicMock()
        sent_msg.id = 7777
        channel.send = AsyncMock(return_value=sent_msg)

        bot_member = make_member(777777, manage_messages=True)
        guild = make_guild(88, channels={600: channel})
        guild.me = bot_member

        ctx = MagicMock()
        ctx.guild = guild
        ctx.channel = channel
        ctx.author = make_member(123, administrator=True, display_name="Admin")
        ctx.interaction = None
        ctx.message = MagicMock()
        ctx.message.delete = AsyncMock()
        ctx.send = AsyncMock()
        ctx.reply = AsyncMock()

        # Purge valid
        await mod_cog.purge.callback(mod_cog, ctx, 5)
        channel.purge.assert_awaited_once()
        ctx.send.assert_awaited()
        assert "Purged **3**" in ctx.send.call_args.kwargs["content"]

        # Purge out of range
        ctx.send.reset_mock()
        await mod_cog.purge.callback(mod_cog, ctx, 200)
        assert "between 1 and 100" in ctx.send.call_args.kwargs["content"]

        # EA, setup, over
        await sess_cog.setup_session.callback(sess_cog, ctx)
        await sess_cog.early_access.callback(sess_cog, ctx, "https://www.roblox.com/share?code=ea1")
        assert bot.db.get_session_link(7777)["url"] == "https://www.roblox.com/share?code=ea1"
        await sess_cog.session_over.callback(sess_cog, ctx)

        # ReleaseLinkView valid + expired
        rel_view = ReleaseLinkView()
        rel_btn = rel_view.children[0]
        bot.db.save_session_link(9001, 88, "release", "https://www.roblox.com/share?code=rel", 123)

        inter = MagicMock(spec=discord.Interaction)
        inter.guild = guild
        inter.message = SimpleNamespace(id=9001)
        inter.client = bot
        inter.response = MagicMock()
        inter.response.send_message = AsyncMock()
        await rel_btn.callback(inter)
        assert "https://www.roblox.com/share?code=rel" in inter.response.send_message.call_args.args[0]

        inter.message = SimpleNamespace(id=999999)
        inter.response.send_message.reset_mock()
        await rel_btn.callback(inter)
        assert "expired" in inter.response.send_message.call_args.args[0]

        # ConfigCog prefix & ping updates
        await cfg_cog.set_prefix.callback(cfg_cog, ctx, "!")
        assert bot.db.get_guild_config(88).prefix == "!"
        role = make_role(55, "PingMe")
        await cfg_cog.set_startup_ping.callback(cfg_cog, ctx, "role", role)
        assert bot.db.get_guild_config(88).startup_ping == "role:55"

        # GeneralCog invite & help
        await gen_cog.invite.callback(gen_cog, ctx)
        await gen_cog.help_command.callback(gen_cog, ctx)
        assert ctx.reply.await_count == 2

        bot.db.close()
