import os
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

class NotionProvider:
    def __init__(self):
        self.notion = Client(auth=os.getenv("NOTION_TOKEN"))
        self.database_id = os.getenv("NOTION_DATABASE_ID")

    def get_approved_questions(self):
        """
        Status == 'Approved' のレコードを取得する
        """
        response = self.notion.databases.query(
            database_id=self.database_id,
            filter={
                "property": "Status",
                "select": {
                    "equals": "Approved"
                }
            }
        )
        return response.get("results", [])

    def update_status(self, page_id, status="Synced"):
        """
        指定したページの Status を更新する
        """
        self.notion.pages.update(
            page_id=page_id,
            properties={
                "Status": {
                    "select": {
                        "name": status
                    }
                }
            }
        )

    def create_question(self, question_data, status="Draft"):
        """
        新しい問題を Notion に登録する (AI生成用)
        """
        properties = {
            "Question": {"title": [{"text": {"content": question_data["question"]}}]},
            "Choice A": {"rich_text": [{"text": {"content": question_data["choice_a"]}}]},
            "Choice B": {"rich_text": [{"text": {"content": question_data["choice_b"]}}]},
            "Choice C": {"rich_text": [{"text": {"content": question_data["choice_c"]}}]},
            "Choice D": {"rich_text": [{"text": {"content": question_data["choice_d"]}}]},
            "Answer": {"select": {"name": question_data["answer"]}},
            "Explanation": {"rich_text": [{"text": {"content": question_data["explanation"]}}]},
            "Part": {"select": {"name": question_data.get("part", "Part5")}},
            "Status": {"select": {"name": status}}
        }
        
        if question_data.get("passage"):
            properties["Passage"] = {"rich_text": [{"text": {"content": question_data["passage"]}}]}

        self.notion.pages.create(
            parent={"database_id": self.database_id},
            properties=properties
        )

    def get_property_text(self, page, property_name):
        """
        Notion ページオブジェクトからテキストプロパティを抽出するユーティリティ
        """
        prop = page["properties"].get(property_name, {})
        prop_type = prop.get("type")
        
        if prop_type == "title":
            return "".join([t["plain_text"] for t in prop["title"]]) if prop["title"] else ""
        elif prop_type == "rich_text":
            return "".join([t["plain_text"] for t in prop["rich_text"]]) if prop["rich_text"] else ""
        elif prop_type == "select":
            return prop["select"]["name"] if prop["select"] else None
        return None
