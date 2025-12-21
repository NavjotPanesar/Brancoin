"""
Tests for EconomyCog slash commands.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from discord.cogs.economy_cog import EconomyCog
from models.models import User, LeagueUser


@pytest.fixture
def mock_interaction():
    """Creates a mock Discord interaction for slash commands."""
    interaction = MagicMock()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user = MagicMock()
    interaction.user.id = 123456789
    interaction.user.display_name = "TestUser"
    interaction.user.display_avatar = MagicMock()
    interaction.user.display_avatar.url = "https://example.com/avatar.png"
    interaction.guild = MagicMock()
    interaction.guild.id = 987654321
    return interaction


@pytest.fixture
def economy_cog(mock_bot, mock_db_service):
    """Creates an EconomyCog instance for testing."""
    return EconomyCog(mock_bot, mock_db_service)


class TestCoinCommand:
    """Tests for /coin command."""

    @pytest.mark.asyncio
    async def test_shows_balance(self, economy_cog, mock_interaction, in_memory_db):
        """Should display user's balance."""
        with in_memory_db() as session:
            user = User()
            user.user_id = "123456789"
            user.guild_id = "987654321"
            user.brancoins = 500
            session.add(user)
            session.commit()

        economy_cog.db.Session = in_memory_db
        await economy_cog.coin.callback(economy_cog, mock_interaction)

        mock_interaction.response.send_message.assert_called_once()
        call_kwargs = mock_interaction.response.send_message.call_args
        embed = call_kwargs.kwargs.get('embed')
        assert embed is not None
        assert any(field.value == "500" for field in embed.fields)

    @pytest.mark.asyncio
    async def test_unknown_user(self, economy_cog, mock_interaction, in_memory_db):
        """Should return error for unknown user."""
        economy_cog.db.Session = in_memory_db
        await economy_cog.coin.callback(economy_cog, mock_interaction)

        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        assert "Who are you?" in str(call_args)

    @pytest.mark.asyncio
    async def test_shows_league_accounts(self, economy_cog, mock_interaction, in_memory_db):
        """Should display linked League accounts."""
        with in_memory_db() as session:
            user = User()
            user.user_id = "123456789"
            user.guild_id = "987654321"
            user.brancoins = 100
            session.add(user)
            session.flush()

            league_user = LeagueUser()
            league_user.summoner_name = "TestPlayer"
            league_user.tag = "NA1"
            league_user.puuid = "test-puuid"
            league_user.trackable = True
            league_user.voteable = True
            league_user.discord_user_id = user.id
            session.add(league_user)
            session.commit()

        economy_cog.db.Session = in_memory_db
        await economy_cog.coin.callback(economy_cog, mock_interaction)

        call_kwargs = mock_interaction.response.send_message.call_args
        embed = call_kwargs.kwargs.get('embed')
        field_values = [field.value for field in embed.fields]
        assert "TestPlayer" in field_values
        assert "NA1" in field_values


class TestBoardCommand:
    """Tests for /board command."""

    @pytest.mark.asyncio
    async def test_shows_leaderboard(self, economy_cog, mock_interaction, in_memory_db, mock_bot):
        """Should display top 10 users."""
        with in_memory_db() as session:
            for i in range(15):
                user = User()
                user.user_id = str(1000 + i)
                user.guild_id = "987654321"
                user.brancoins = 100 * (15 - i)  # Descending order
                session.add(user)
            session.commit()

        economy_cog.db.Session = in_memory_db
        await economy_cog.board.callback(economy_cog, mock_interaction)

        mock_interaction.response.send_message.assert_called_once()
        call_kwargs = mock_interaction.response.send_message.call_args
        embed = call_kwargs.kwargs.get('embed')
        assert embed is not None
        assert len(embed.fields) <= 10  # Max 10 users


class TestBegCommand:
    """Tests for /beg command."""

    @pytest.mark.asyncio
    async def test_gives_coins_when_broke(self, economy_cog, mock_interaction, in_memory_db):
        """Should give 10 coins when user has 0 or less."""
        with in_memory_db() as session:
            user = User()
            user.user_id = "123456789"
            user.guild_id = "987654321"
            user.brancoins = 0
            session.add(user)
            session.commit()

        economy_cog.db.Session = in_memory_db
        await economy_cog.beg.callback(economy_cog, mock_interaction)

        with in_memory_db() as session:
            user = session.query(User).first()
            assert user.brancoins == 10

        call_args = mock_interaction.response.send_message.call_args
        assert "brokie" in str(call_args).lower()

    @pytest.mark.asyncio
    async def test_rejects_non_broke_user(self, economy_cog, mock_interaction, in_memory_db):
        """Should reject users with positive balance."""
        with in_memory_db() as session:
            user = User()
            user.user_id = "123456789"
            user.guild_id = "987654321"
            user.brancoins = 50
            session.add(user)
            session.commit()

        economy_cog.db.Session = in_memory_db
        await economy_cog.beg.callback(economy_cog, mock_interaction)

        call_args = mock_interaction.response.send_message.call_args
        assert "not broke enough" in str(call_args).lower()

        # Balance should be unchanged
        with in_memory_db() as session:
            user = session.query(User).first()
            assert user.brancoins == 50

    @pytest.mark.asyncio
    async def test_rejects_repeat_beggar(self, economy_cog, mock_interaction, in_memory_db):
        """Should only allow begging once."""
        with in_memory_db() as session:
            user = User()
            user.user_id = "123456789"
            user.guild_id = "987654321"
            user.brancoins = 0
            session.add(user)
            session.commit()

        economy_cog.db.Session = in_memory_db

        # First beg succeeds
        await economy_cog.beg.callback(economy_cog, mock_interaction)

        # Set balance back to 0 and try again
        with in_memory_db() as session:
            user = session.query(User).first()
            user.brancoins = 0
            session.commit()

        mock_interaction.response.send_message.reset_mock()
        await economy_cog.beg.callback(economy_cog, mock_interaction)

        call_args = mock_interaction.response.send_message.call_args
        assert "already begged" in str(call_args).lower()


class TestGiftCommand:
    """Tests for /gift command."""

    @pytest.fixture
    def mock_recipient(self):
        """Creates a mock recipient member."""
        recipient = MagicMock()
        recipient.id = 999888777
        recipient.mention = "<@999888777>"
        return recipient

    @pytest.mark.asyncio
    async def test_successful_gift(self, economy_cog, mock_interaction, in_memory_db, mock_recipient):
        """Should transfer coins between users."""
        with in_memory_db() as session:
            sender = User()
            sender.user_id = "123456789"
            sender.guild_id = "987654321"
            sender.brancoins = 100
            session.add(sender)

            receiver = User()
            receiver.user_id = "999888777"
            receiver.guild_id = "987654321"
            receiver.brancoins = 50
            session.add(receiver)
            session.commit()

        economy_cog.db.Session = in_memory_db
        economy_cog.freebie_chance = 0  # Disable freebie for predictable test

        await economy_cog.gift.callback(economy_cog, mock_interaction, mock_recipient, 30)

        with in_memory_db() as session:
            sender = session.query(User).filter(User.user_id == "123456789").first()
            receiver = session.query(User).filter(User.user_id == "999888777").first()
            assert sender.brancoins == 70  # 100 - 30
            assert receiver.brancoins == 80  # 50 + 30

    @pytest.mark.asyncio
    async def test_insufficient_funds(self, economy_cog, mock_interaction, in_memory_db, mock_recipient):
        """Should reject gift when sender doesn't have enough."""
        with in_memory_db() as session:
            sender = User()
            sender.user_id = "123456789"
            sender.guild_id = "987654321"
            sender.brancoins = 20
            session.add(sender)

            receiver = User()
            receiver.user_id = "999888777"
            receiver.guild_id = "987654321"
            receiver.brancoins = 50
            session.add(receiver)
            session.commit()

        economy_cog.db.Session = in_memory_db
        await economy_cog.gift.callback(economy_cog, mock_interaction, mock_recipient, 100)

        call_args = mock_interaction.response.send_message.call_args
        assert "facilities" in str(call_args).lower()

        # Balances unchanged
        with in_memory_db() as session:
            sender = session.query(User).filter(User.user_id == "123456789").first()
            receiver = session.query(User).filter(User.user_id == "999888777").first()
            assert sender.brancoins == 20
            assert receiver.brancoins == 50

    @pytest.mark.asyncio
    async def test_negative_amount_rejected(self, economy_cog, mock_interaction, in_memory_db, mock_recipient):
        """Should reject negative gift amounts."""
        economy_cog.db.Session = in_memory_db
        await economy_cog.gift.callback(economy_cog, mock_interaction, mock_recipient, -50)

        call_args = mock_interaction.response.send_message.call_args
        assert "positive" in str(call_args).lower()

    @pytest.mark.asyncio
    async def test_zero_amount_rejected(self, economy_cog, mock_interaction, in_memory_db, mock_recipient):
        """Should reject zero gift amount."""
        economy_cog.db.Session = in_memory_db
        await economy_cog.gift.callback(economy_cog, mock_interaction, mock_recipient, 0)

        call_args = mock_interaction.response.send_message.call_args
        assert "positive" in str(call_args).lower()

    @pytest.mark.asyncio
    async def test_self_gift_rejected(self, economy_cog, mock_interaction, in_memory_db):
        """Should reject gifting to yourself."""
        mock_self = MagicMock()
        mock_self.id = 123456789  # Same as interaction.user.id
        mock_self.mention = "<@123456789>"

        economy_cog.db.Session = in_memory_db
        await economy_cog.gift.callback(economy_cog, mock_interaction, mock_self, 50)

        call_args = mock_interaction.response.send_message.call_args
        assert "yourself" in str(call_args).lower()

    @pytest.mark.asyncio
    async def test_freebie_gift(self, economy_cog, mock_interaction, in_memory_db, mock_recipient):
        """Freebie gift should not deduct from sender."""
        with in_memory_db() as session:
            sender = User()
            sender.user_id = "123456789"
            sender.guild_id = "987654321"
            sender.brancoins = 100
            session.add(sender)

            receiver = User()
            receiver.user_id = "999888777"
            receiver.guild_id = "987654321"
            receiver.brancoins = 50
            session.add(receiver)
            session.commit()

        economy_cog.db.Session = in_memory_db
        economy_cog.freebie_chance = 1.0  # Always freebie

        await economy_cog.gift.callback(economy_cog, mock_interaction, mock_recipient, 30)

        with in_memory_db() as session:
            sender = session.query(User).filter(User.user_id == "123456789").first()
            receiver = session.query(User).filter(User.user_id == "999888777").first()
            assert sender.brancoins == 100  # Unchanged!
            assert receiver.brancoins == 80  # Still received

        call_args = mock_interaction.response.send_message.call_args
        assert "vivian" in str(call_args).lower()
