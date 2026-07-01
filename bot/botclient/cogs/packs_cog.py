import asyncio
from io import BytesIO
from typing import List
import discord
from discord import app_commands
from discord.ext import commands
import random
from models.dbcontainer import DbService
from models.models import BoosterCard, BoosterPack, BoosterSegment, Card, OwnedCard, User
from botclient.drawutils import DrawUtils
from .base_cog import BaseCog


class PacksCog(BaseCog):
    """Booster pack commands: buying and opening packs."""

    @app_commands.command(name="buypack", description="Buy and open a booster pack")
    @app_commands.describe(pack_id="ID of the pack to buy")
    async def buypack(self, interaction: discord.Interaction, pack_id: str):
        await interaction.response.defer()

        with self.db.Session() as session:
            user = self.get_user(session, str(interaction.user.id), str(interaction.guild.id))
            pack = session.query(BoosterPack).filter(BoosterPack.id == pack_id).first()

            if pack is None:
                await interaction.followup.send("Can't find pack with that name")
                return

            if user.brancoins < pack.cost:
                await interaction.followup.send("You broke son")
                return

            drawn_card_segments = self._draw_cards_from_pack(pack)
            for drawn_card_segment in drawn_card_segments:
                for drawn_card in drawn_card_segment[1]:
                    owned_card = OwnedCard()
                    owned_card.card = drawn_card
                    user.owned_cards.append(owned_card)

            user.brancoins -= pack.cost
            session.add(user)
            session.commit()

            await interaction.followup.send(f"Opening a {pack_id} pack!")

            for drawn_card_segment in drawn_card_segments:
                files = await self._display_segment(drawn_card_segment[0], drawn_card_segment[1])
                await asyncio.sleep(3)
                await interaction.channel.send(
                    f"Looks like we have some {drawn_card_segment[0].id} cards...",
                    files=files
                )

            await interaction.channel.send("Congrats on the new cards!")

    def _draw_cards_from_pack(self, pack: BoosterPack) -> List[tuple[BoosterSegment, List[Card]]]:
        drawn_cards: List[tuple[BoosterSegment, List[Card]]] = []
        for segment in pack.booster_segments:
            weights = []
            cards = []
            for booster_card in segment.booster_cards:
                weights.append(booster_card.chance)
                cards.append(booster_card.card)
            if len(cards) > 0 and len(weights) > 0 and len(cards) == len(weights):
                drawn_cards.append((segment, random.choices(cards, weights, k=segment.num_cards_to_draw)))
        return drawn_cards

    async def _display_segment(self, segment: BoosterSegment, cards: List[Card]):
        bg = "boostermat.jpeg" if segment.bg_fname is None else segment.bg_fname
        return await self._card_spread(cards, bg)

    async def _card_spread(self, cards, bg):
        card_pages: List[List[Card]] = self._split(cards, 6)
        discord_files: List[discord.File] = []
        for idx, card_page in enumerate(card_pages):
            grid = (len(card_page), 1)
            inv_img = await DrawUtils.draw_inv_card_spread(
                card_page, (1400, 400), grid, draw_blanks=True, bg=bg
            )
            buffered = BytesIO()
            inv_img.save(buffered, format="PNG")
            discord_files.append(discord.File(BytesIO(buffered.getvalue()), filename=f"page{idx}.png"))
        return discord_files

    def _split(self, arr, size):
        return [arr[i:i + size] for i in range(0, len(arr), size)]
