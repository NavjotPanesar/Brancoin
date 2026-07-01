from sqlalchemy import text
from models.models import Card, OwnedCard, User


def find_card_by_text(session, owner: User, search_text: str) -> OwnedCard | None:
    """Find a card by fuzzy text match against title or description.

    Uses PostgreSQL's pg_trgm similarity function for fuzzy matching.
    Returns the owned card with highest similarity score.
    """
    query_text = text(
        "Select ownedcards.id, cards.cost, similarity(cards.title, :str_search) as sim "
        "from ownedcards inner join cards on ownedcards.card_id = cards.id "
        "where ownedcards.owner_id = :ownerid "
        "UNION ALL "
        "Select ownedcards.id, cards.cost, similarity(cards.description, :str_search) as sim "
        "from ownedcards inner join cards on ownedcards.card_id = cards.id "
        "where ownedcards.owner_id = :ownerid "
        "order by sim desc, cost desc "
    )
    closest_owned_card = session.execute(
        query_text,
        {"ownerid": owner.id, "str_search": search_text}
    ).first()

    if closest_owned_card is None:
        return None

    owned_card = session.query(OwnedCard).join(
        Card, OwnedCard.card
    ).filter(OwnedCard.id == closest_owned_card[0]).first()
    return owned_card
