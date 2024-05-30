import base64
from io import BytesIO
import PIL
from bottle import Bottle, route, request 
from discord.drawutils import DrawUtils
from models.models import Card
import models
from models.dbcontainer import DbContainer, DbService
from dependency_injector.wiring import Provide, inject
from envvars import Env
from bottle import route, run, template, post, get, response
from cardmaker import CardConstructor

@post('/image')
@inject
def upload_image(dbservice: DbService = Provide[DbContainer.service]):
    image = models.Image()
    print(request.files.get("image"))
    image.bin = request.files.get("image").file.read()
    image.label = request.forms.get("label")

    with dbservice.Session() as session:
        session.add(image)
        session.commit()

    return "done"

@get('/preview')
@inject
def get_image(dbservice: DbService = Provide[DbContainer.service]):
    id = request.query['id']

    with dbservice.Session() as session:
        card = session.query(Card).filter(Card.id == id).first()
        response.set_header('Content-type', 'image/png')
        return DrawUtils.card_to_byte_image(card)

    return "done"



def start():


    run(host='0.0.0.0', port=Env.web_port)