import base64
import datetime
from io import BytesIO
import math
import os
from PIL import Image, ImageFont, ImageDraw
from cachetools import cached
from cachetools.keys import hashkey
from discord import Message
import discord
from sqlalchemy import func
from discord.drawutils import DrawUtils
from models.dbcontainer import DbService
from models.models import BoosterCard, BoosterPack, Card, Shop, User
from discord.basecommand import BaseCommand
from discord.ext.commands import Bot


class ViewShop(BaseCommand):
    prefix = "bran shop"
    usage = prefix

    card_width = 349
    card_height = 509
    card_y = 183
    card_coords = [ 
        (55, card_y),
        (433, card_y),
        (811, card_y),
        (1186, card_y),
    ]

    text_margin_x = 20
    text_margin_y = 12
    text_y = 718 + text_margin_y
    text_width = 158
    text_height = 73
    text_coords = [
        (199 + text_margin_x, text_y),
        (582 + text_margin_x, text_y),
        (960 + text_margin_x, text_y),
        (1337 + text_margin_x, text_y),
    ]


    async def process(self, ctx, message: Message, dbservice: DbService):
        if not self.does_prefix_match(self.prefix, message.content):
            return
        
        with dbservice.Session() as session: 
            if session.query(Shop).filter(Shop.date_added == datetime.date.today()).count() < 4:
                print("no shop, populating")
                featured_cards = session.query(Card).filter(Card.featured == True).all()
                drawn_cards = []
                drawn_cards.append(session.query(Card).filter(Card.shoppable == True, Card.cost <= 100).order_by(func.random()).first())
                drawn_cards.append(session.query(Card).filter(Card.shoppable == True, Card.cost > 100, Card.cost <= 500).order_by(func.random()).first())
                drawn_cards.append(session.query(Card).filter(Card.shoppable == True, Card.cost > 100).order_by(func.random()).first())
                drawn_cards.append(session.query(Card).filter(Card.shoppable == True, Card.cost > 1000).order_by(func.random()).first())
                drawn_cards.append(session.query(Card).filter(Card.shoppable == True).order_by(func.random()).first())
                drawn_cards.append(session.query(Card).filter(Card.shoppable == True).order_by(func.random()).first())

                filtered_drawn_cards = list(filter(lambda x: x is not None, drawn_cards))
                
                cards_to_add = []
                for featuredCard in featured_cards:
                    cards_to_add.append(featuredCard)
                while len(cards_to_add) < 4:
                    newShopCard = Shop()
                    cards_to_add.append(filtered_drawn_cards.pop(0))
                while len(cards_to_add) < 4:
                    cards_to_add.append(cards_to_add[0])

                for card_to_add in cards_to_add:
                    if card_to_add:
                        newShopCard = Shop()
                        print(card_to_add)
                        newShopCard.card = card_to_add
                        newShopCard.date_added = datetime.date.today()
                        session.add(newShopCard)

                session.commit()

        
        cards = []
        card_images = []
        card_labels = []
        card_costs = []
        with dbservice.Session() as session: 
            shop_items = session.query(Shop).join(Card, Shop.card).filter(Shop.date_added == datetime.date.today()).order_by(Card.cost.asc(), Card.id.asc()).all()
            for idx, shop_item in enumerate(shop_items):
                cards.append(shop_item.card)
                card_images.append(DrawUtils.card_to_image(shop_item.card))
                card_costs.append(shop_item.card.cost)
                card_labels.append(f"[bran buy {idx + 1}] to buy {shop_item.card.title} {shop_item.card.card_style} for [**{shop_item.card.cost}** {self.custom_emoji}]!")
        
        shop_image = None
        if len(card_images) == 4:
            shop_image = self.draw_shop_image(card_images, card_costs)
        else: 
            shop_image = await self.draw_shop_image_flex(cards)
        discord_shop_item = discord.File(shop_image, filename="shop.png")
        card_label_joined = ',\n'.join(card_labels)
        await message.reply(f"**Welcome to the Bran Shop!**\n{card_label_joined}", file=discord_shop_item)
        await self.show_pack_shop(dbservice, message)

    def draw_shop_image(self, card_images, card_costs):
        shop_map = Image.open(os.path.dirname(__file__) + "/../../assets/shopmat.png")
        font = ImageFont.truetype(os.path.dirname(__file__) + "/../../assets/Jersey M54.ttf", 40)
        shop_draw = ImageDraw.Draw(shop_map)
        for idx, card_image in enumerate(card_images):
            shop_map.paste(card_image.resize((self.card_width, self.card_height)), self.card_coords[idx])
            shop_draw.text(self.text_coords[idx], str(card_costs[idx]), (0, 0, 0), font)

        buffered = BytesIO()
        shop_map.save(buffered, format="PNG")
        return BytesIO(buffered.getvalue())
    
    async def draw_shop_image_flex(self, cards):
        shop_map = await DrawUtils.draw_inv_card_spread(cards, (math.floor(1600/4*len(cards)), 900), (len(cards), 1), draw_blanks=False)
        buffered = BytesIO()
        shop_map.save(buffered, format="PNG")
        return BytesIO(buffered.getvalue())
    
    async def show_pack_shop(self, dbservice: DbService, message: discord.Message):
        with dbservice.Session() as session:
            packs = session.query(BoosterPack).all()
            if packs is None or len(packs) == 0:
                await message.reply("can't find any packs")
                return
            
            source = session.query(User).filter(User.user_id == str(message.author.id), User.guild_id == str(message.guild.id)).first()
            owned_card_ids = [x.card_id for x in source.owned_cards]
            missing_cards_text = []
            for pack in packs:
                distinct_cards_in_pack = session.query((func.distinct(BoosterCard.card_id))).filter(BoosterCard.booster_pack_id == pack.id).all()
                distinct_card_ids = [x.tuple()[0] for x in distinct_cards_in_pack]
                missing_card_ids = [x for x in distinct_card_ids if x not in owned_card_ids]
                missing_cards_text.append(f"\nYou're missing {len(missing_card_ids)} cards from this pack!")

            embed = discord.Embed(title=f"Pack Shop!", description="", color=0xccffff)
            embed.set_author(name="Check out these boosters!", icon_url="https://i.imgur.com/L4Ps6O5.png")
            
            for idx, pack in enumerate(packs):
                embed.add_field(name=f"bran buypack {str(pack.id)}", value=str(pack.desc), inline=True)
                embed.add_field(name=f"costs {self.custom_emoji} {str(pack.cost)}", value=missing_cards_text[idx] , inline=True)
                embed.add_field(name="", value="", inline=False)

            embed.set_image(url="https://i.imgur.com/NifcNgd.jpeg")

            await message.reply(embed=embed)