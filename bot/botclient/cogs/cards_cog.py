import math
from io import BytesIO
from typing import List
import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import text
from models.dbcontainer import DbService
from models.models import Card, OwnedCard, User
from botclient.drawutils import DrawUtils
from botclient.helpers.card_utils import find_card_by_text
from .base_cog import BaseCog


class CardsCog(BaseCog):
    """Card collection commands: inventory, viewing, summoning, and destroying."""

    @app_commands.command(name="inv", description="View your card inventory")
    async def inventory(self, interaction: discord.Interaction):
        await interaction.response.defer()

        with self.db.Session() as session:
            guy = self.get_user(session, str(interaction.user.id), str(interaction.guild.id))
            if guy:
                cards = []
                for owned_card in guy.owned_cards:
                    cards.append(owned_card.card)

                if len(cards) <= 0:
                    await interaction.followup.send("No cards")
                    return

                max_x = 6
                max_y = 4
                card_pages: List[List[Card]] = self._split(cards, max_x * max_y)
                discord_files: List[discord.File] = []
                idx_counter = 1

                for idx, card_page in enumerate(card_pages):
                    img_size = (1600, 1200)
                    grid = (max_x, max_y)
                    if len(card_page) <= max_x * 1:
                        grid = (math.ceil(len(card_page) / 1), 1)
                    elif len(card_page) <= max_x * 2:
                        grid = (math.ceil(len(card_page) / 2), 2)
                    elif len(card_page) <= max_x * 3:
                        grid = (math.ceil(len(card_page) / 3), 3)
                    else:
                        grid = (math.ceil(len(card_page) / 4), 4)
                        img_size = (1600, 1600)

                    inv_img = await DrawUtils.draw_inv_card_spread(
                        card_page, img_size, grid,
                        draw_blanks=True, draw_idx=True, idx_offset=idx_counter
                    )
                    buffered = BytesIO()
                    inv_img.save(buffered, format="PNG")
                    discord_files.append(
                        discord.File(BytesIO(buffered.getvalue()), filename=f"page{idx}.png")
                    )
                    idx_counter += len(card_page)

                await interaction.followup.send("Inventory:", files=discord_files)
            else:
                await interaction.followup.send("Who are you?")

    @app_commands.command(name="viewcard", description="View a specific card from your inventory")
    @app_commands.describe(card="Card index number (1, 2, 3...) or search text")
    async def viewcard(self, interaction: discord.Interaction, card: str):
        await interaction.response.defer()

        with self.db.Session() as session:
            guy = self.get_user(session, str(interaction.user.id), str(interaction.guild.id))
            if not guy:
                await interaction.followup.send("Who are you?")
                return

            selected_card = None
            if self._represents_int(card):
                card_idx = int(card) - 1
                if card_idx < len(guy.owned_cards) and card_idx >= 0:
                    selected_card = guy.owned_cards[card_idx].card
            else:
                owned_card = find_card_by_text(session, guy, card)
                if owned_card:
                    selected_card = owned_card.card

            if selected_card is not None:
                file = discord.File(
                    DrawUtils.card_to_byte_image(selected_card),
                    filename="card.png"
                )
                await interaction.followup.send(
                    f"Behold! I'll activate {selected_card.title}!!!",
                    file=file
                )
            else:
                await interaction.followup.send("Card not found")

    @app_commands.command(name="summon", description="Summon a card with animation")
    @app_commands.describe(card="Card index number (1, 2, 3...) or search text")
    async def summon(self, interaction: discord.Interaction, card: str):
        await interaction.response.defer()

        with self.db.Session() as session:
            guy = self.get_user(session, str(interaction.user.id), str(interaction.guild.id))
            if not guy:
                await interaction.followup.send("Who are you?")
                return

            selected_card = None
            if self._represents_int(card):
                card_idx = int(card) - 1
                if card_idx < len(guy.owned_cards) and card_idx >= 0:
                    selected_card = guy.owned_cards[card_idx].card
            else:
                owned_card = find_card_by_text(session, guy, card)
                if owned_card:
                    selected_card = owned_card.card

            if selected_card is not None:
                file = discord.File(
                    DrawUtils.summon(selected_card),
                    filename="summon.gif"
                )
                await interaction.followup.send(
                    f"Behold! I'll activate {selected_card.title}!!!",
                    file=file
                )
            else:
                await interaction.followup.send("Card not found")

    @app_commands.command(name="torch", description="Destroy a card to get coins back")
    @app_commands.describe(card_index="Index of the card to destroy (from /inv)")
    async def torch(self, interaction: discord.Interaction, card_index: int):
        with self.db.Session() as session:
            guy = self.get_user(session, str(interaction.user.id), str(interaction.guild.id))
            card_idx = card_index - 1

            if guy and card_idx >= 0 and card_idx < len(guy.owned_cards):
                owned_card = guy.owned_cards[card_idx]
                value = owned_card.card.cost
                title = owned_card.card.title
                refund = math.ceil(value / 6)
                guy.brancoins += refund
                session.query(OwnedCard).filter(OwnedCard.id == owned_card.id).delete()
                session.add(guy)
                session.commit()
                await interaction.response.send_message(
                    f"{title} has been sent to the shadow realm!!! {refund}{self.custom_emoji} restored.\n"
                    f"**card inventory indexes have changed, be careful when deleting in a chain**"
                )
            else:
                await interaction.response.send_message("Card not found", ephemeral=True)

    @app_commands.command(name="torchdupes", description="Destroy up to 10 duplicate cards for coins")
    async def torchdupes(self, interaction: discord.Interaction):
        with self.db.Session() as session:
            guy = self.get_user(session, str(interaction.user.id), str(interaction.guild.id))
            if not guy:
                await interaction.response.send_message("Who are you?", ephemeral=True)
                return

            query_text = text(
                "select id FROM "
                "( "
                    "select ownedcards.card_id, min(ownedcards.id) as saved_id "
                    "from ownedcards "
                    "where owner_id=:ownerid "
                    "group by ownedcards.card_id having count(*) > 1 "
                ") as dupes_to_keep "
                "INNER JOIN "
                "ownedcards "
                "on ownedcards.card_id = dupes_to_keep.card_id "
                "where ownedcards.id > dupes_to_keep.saved_id AND owner_id=:ownerid limit 10"
            )
            dupe_owned_card_ids = session.execute(query_text, {"ownerid": guy.id}).scalars()
            outputs = []

            for dupe_owned_card_id in dupe_owned_card_ids:
                dupe_owned_card = session.query(OwnedCard).filter(
                    OwnedCard.id == dupe_owned_card_id
                ).first()
                value = dupe_owned_card.card.cost
                title = dupe_owned_card.card.title
                refund = math.ceil(value / 6)
                guy.brancoins += refund
                session.add(guy)
                session.query(OwnedCard).filter(OwnedCard.id == dupe_owned_card_id).delete()
                outputs.append(f"{title} for {refund}{self.custom_emoji}")

            if outputs:
                output = ', '.join(outputs)
                await interaction.response.send_message(f"torching: {output}")
                session.commit()
            else:
                await interaction.response.send_message("No duplicates found", ephemeral=True)

    def _split(self, arr, size):
        return [arr[i:i + size] for i in range(0, len(arr), size)]

    def _represents_int(self, s):
        try:
            int(s)
        except ValueError:
            return False
        return True
