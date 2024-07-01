import datetime
from typing import List
from typing import Optional
from sqlalchemy import BLOB, Float, ForeignKey, ForeignKeyConstraint, Integer, LargeBinary, PrimaryKeyConstraint, UniqueConstraint, null, true
from sqlalchemy import String
import sqlalchemy
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from models.base import Base

class User(Base):
    __tablename__ = "user_account"
    id = mapped_column(Integer, primary_key=True, autoincrement=True, unique=True)
    user_id: Mapped[str]
    guild_id: Mapped[str]
    brancoins  = mapped_column(Integer, server_default="10")

    league_users: Mapped[List["LeagueUser"]]= relationship(back_populates="discord_user")
    owned_cards: Mapped[List["OwnedCard"]]= relationship(back_populates="owner")

    __table_args__ = (
        UniqueConstraint('user_id', 'guild_id', name='user_guild_uc'),
    )
    
    def __repr__(self) -> str:
        return f"User(id={self.user_id!r}, guild={self.guild_id!r})"

class LeagueUser(Base):
    __tablename__ = "league_user"
    id = mapped_column(Integer, primary_key=True, autoincrement=True, unique=True)
    summoner_name: Mapped[str]
    tag: Mapped[str]
    trackable: Mapped[bool]
    voteable: Mapped[bool]
    
    discord_user_id = mapped_column(Integer, ForeignKey("user_account.id"))
    discord_user: Mapped["User"] = relationship(back_populates="league_users")
    # todo: make this unique by summoner_name, tag so we don't have multiple discord_users possible for a league_user

    def __repr__(self) -> str:
        return f"tag(id={self.tag!r}, summoner_name={self.summoner_name!r}, trackable={self.trackable!r}, voteable={self.voteable!r})"
    
class Match(Base):
    __tablename__ = "match"
    match_id: Mapped[str] = mapped_column(primary_key=true)
    finished: Mapped[bool] = mapped_column(server_default="False")
    start_time: Mapped[datetime.datetime] 

    match_players: Mapped[List["MatchPlayer"]] = relationship(back_populates="match")
    votes: Mapped[List["Votes"]] = relationship()

    def get_time_since_start(self) -> datetime.timedelta:
        return datetime.datetime.now() - self.start_time
    
    def __repr__(self) -> str:
        return f"tag(match_id={self.match_id!r}, finished={self.finished!r}, start_time={self.start_time!r})"

class MatchPlayer(Base):
    __tablename__ = "match_player"
    match_id: Mapped[str] = mapped_column(ForeignKey("match.match_id"), primary_key=True)
    league_user_id: Mapped[Integer] = mapped_column(ForeignKey("league_user.id"), primary_key=True)
    champion: Mapped[str]

    league_user: Mapped["LeagueUser"] = relationship()
    match: Mapped["Match"] = relationship()

    __table_args__ = (
        PrimaryKeyConstraint('match_id', 'league_user_id'),
    )

    def __repr__(self) -> str:
        return f"MatchPlayer(match_id={self.match_id!r}, league_user_id={self.league_user_id!r}, champion={self.champion!r},)"


class Guild(Base):
    __tablename__ = "guild"
    guild_id: Mapped[str] = mapped_column(primary_key=True, unique=True)
    brancoins:Mapped[int] = mapped_column(server_default="10") # jackpot
    broadcast_channel_id: Mapped[str] = mapped_column(nullable=True)
    broadcast_role_id: Mapped[str] = mapped_column(nullable=True)

    def __repr__(self) -> str:
        return f"Guild(guild_id={self.guild_id!r}, brancoins={self.brancoins!r})"

class Votes(Base):
    __tablename__ = "votes"
    id = mapped_column(Integer, primary_key=True, autoincrement=True, unique=True)
    voter_id: Mapped[str] = mapped_column(ForeignKey("user_account.id"))
    match_id: Mapped[str] = mapped_column(ForeignKey("match.match_id"))
    target_league_player: Mapped[str] = mapped_column(ForeignKey("league_user.id"), nullable=True)
    processed: Mapped[bool] = mapped_column(server_default="False")
    type_of_vote: Mapped[int]
    brancoins: Mapped[int]

    voter: Mapped["User"] = relationship()

    def __repr__(self) -> str:
        return f"Votes(id={self.id!r}, voter={self.voter!r}, target_league_player={self.target_league_player!r}, type_of_vote={self.type_of_vote})"
    

class Image(Base):
    __tablename__ = "images"
    label = mapped_column(String, primary_key=True, unique=True)
    bin = mapped_column(LargeBinary)

    def __repr__(self) -> str:
        return f"Images(label={self.label!r}"
    
class OwnedCard(Base):
    __tablename__ = "ownedcards"
    
    id = mapped_column(Integer, primary_key=True, autoincrement=True, unique=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("user_account.id"))
    card_id: Mapped[Integer] = mapped_column(ForeignKey("cards.id"))

    owner: Mapped["User"] = relationship(back_populates="owned_cards")
    card: Mapped["Card"] = relationship()

    def __repr__(self) -> str:
        return f"OwnedCard(id={self.id!r}, owner_id={self.owner_id!r}, card_id={self.card_id!r},)"
    
class Card(Base):
    __tablename__ = "cards"
    id = mapped_column(Integer, primary_key=True, autoincrement=True, unique=True)
    card_style: Mapped[str] 
    title: Mapped[str] = mapped_column(String)
    attribute: Mapped[str] 
    level: Mapped[str] 
    type: Mapped[str] 
    description: Mapped[str] 
    atk: Mapped[str] 
    defe: Mapped[str] 
    cost: Mapped[int] 
    image_label: Mapped[str] = mapped_column(ForeignKey("images.label"))
    image: Mapped["Image"] = relationship()
    shoppable: Mapped[bool] = mapped_column(server_default="t")
    featured: Mapped[bool] = mapped_column(server_default="f")
    bonuses: Mapped[List["CardBonus"]] = relationship()

    def __repr__(self) -> str:
        return f"Card(title={self.title!r}"
    
class CardBonus(Base):
    __tablename__ = "cardbonuses"
    id = mapped_column(Integer, primary_key=True, autoincrement=True, unique=True)
    card_id: Mapped[Integer] = mapped_column(ForeignKey("cards.id"))
    bonus_type: Mapped[int]

    def __repr__(self) -> str:
        return f"CardBonus(id={self.id!r}, card_id={self.card_id!r}, bonus_type={self.bonus_type!r})"

    
class Shop(Base):
    __tablename__ = "shop"
    id = mapped_column(Integer, primary_key=True, autoincrement=True, unique=True)
    card_id: Mapped[Integer] = mapped_column(ForeignKey("cards.id"))
    card: Mapped["Card"] = relationship()
    date_added: Mapped[datetime.date] = mapped_column(server_default=str(datetime.date.today()))

class BoosterPack(Base):
    __tablename__ = "booster_pack"
    id = mapped_column(String, primary_key=True, unique=True)
    cost: Mapped[int]
    image_label: Mapped[str] = mapped_column(ForeignKey("images.label"))
    image: Mapped["Image"] = relationship()
    desc: Mapped[str] = mapped_column(String, server_default="")
    booster_segments: Mapped[List["BoosterSegment"]] = relationship()

class BoosterSegment(Base):
    __tablename__ = "booster_segments"
    # id = mapped_column(Integer, primary_key=True, autoincrement=True, unique=True)
    booster_pack_id: Mapped[str] = mapped_column(ForeignKey("booster_pack.id"),  primary_key=True)
    id = mapped_column(String, primary_key=True)
    num_cards_to_draw: Mapped[int]
    booster_cards: Mapped[List["BoosterCard"]] = relationship()
    bg_fname: Mapped[str] = mapped_column(String, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint('booster_pack_id', 'id'),
    )

class BoosterCard(Base):
    __tablename__ = "booster_card"
    id = mapped_column(Integer, primary_key=True, autoincrement=True, unique=True)
    card_id: Mapped[Integer] = mapped_column(ForeignKey("cards.id"))
    booster_pack_id: Mapped[str]
    booster_segment_id: Mapped[str] 
    chance: Mapped[float]
    card: Mapped["Card"] = relationship()

    __table_args__ = (ForeignKeyConstraint(["booster_pack_id", "booster_segment_id"],
                                           ["booster_segments.booster_pack_id", "booster_segments.id"]),
                      {})