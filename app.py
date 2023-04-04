from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage, ImageSendMessage
from flask import Flask, request, abort
from dotenv import load_dotenv
import os
from pathlib import Path
from clip_interrogator import Config, Interrogator
from PIL import Image
import openai

app = Flask(__name__)

load_dotenv()
YOUR_CHANNEL_ACCESS_TOKEN = os.getenv('YOUR_CHANNEL_ACCESS_TOKEN')
YOUR_CHANNEL_SECRET = os.getenv('YOUR_CHANNEL_SECRET')
API_KEY = os.getenv('API_KEY')
line_bot_api = LineBotApi(YOUR_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(YOUR_CHANNEL_SECRET)
openai.api_key = API_KEY

class ChatGPT:
    def __init__(self, system_setting):
        self.system = {"role": "system", "content": system_setting}
        self.input_list = [self.system]
        self.logs = []

    def input_message(self, input_text):
        self.input_list.append({"role": "user", "content": input_text})
        result = openai.ChatCompletion.create(
            model="gpt-3.5-turbo", messages=self.input_list
        )
        self.logs.append(result)
        self.input_list.append(
            {"role": "assistant", "content": result.choices[0].message.content}
        )

ci = Interrogator(Config(clip_model_name="ViT-L-14/openai"))

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    message_id = event.message.id
    # message_idから画像のバイナリデータを取得
    message_content = line_bot_api.get_message_content(message_id)

    with open(Path(f"input.jpg").absolute(), "wb") as f:
        # バイナリを1024バイトずつ書き込む
        for chunk in message_content.iter_content():
            f.write(chunk)

    line_bot_api.push_message(event.source.user_id, TextSendMessage(text="現在、映画を製作中です..."))
    image = Image.open('input.jpg')
    text = ci.interrogate(image)
    movietitlemaker = ChatGPT(system_setting="あなたは映画作成者です。受け取った英文はある画像の内容を表したプロンプトです。この画像をパッケージとする映画を作るときにワクワクするようなタイトルと100文字程度のあらすじを日本語で生成して出力してください。ただし文字数などは出力しないこと。")
    movietitlemaker.input_message(text)
    movie = movietitlemaker.input_list[-1]["content"]
    # critic = ChatGPT(system_setting="あなたは映画評論家です。受け取ったある映画のタイトルとあらすじから称賛コメントと批判コメントをそれぞれ50文字程度で生成して出力してください。")
    critic = ChatGPT(system_setting="あなたは映画評論家です。受け取った映画のタイトルとあらすじから映画を評価し、70文字程度で評価を述べてください。また、100点満点で点数をつけてください。出力は【点数】の表記から始めて、評価の文章は【評価】で始めてください。")
    critic.input_message(movie)
    criticism = critic.input_list[-1]["content"]
    line_bot_api.push_message(event.source.user_id, TextSendMessage(text=movie))
    line_bot_api.push_message(event.source.user_id, TextSendMessage(text=criticism))
    
if __name__ == "__main__":
    app.run()
