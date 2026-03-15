import sys
import json
import argparse
from notion_provider import NotionProvider

notion_provider = NotionProvider()

def push_question(json_str):
    """エージェントが生成した JSON を Notion に保存する"""
    try:
        data = json.loads(json_str)
        notion_provider.create_question(data, status="Draft")
        print("Successfully pushed to Notion as Draft.")
    except Exception as e:
        print(f"Error pushing question: {e}")

def list_drafts():
    """Notion から Draft 状態の問題を取得して表示する"""
    try:
        pages = notion_provider.get_draft_questions()
        results = []
        for page in pages:
            results.append({
                "page_id": page["id"],
                "question": notion_provider.get_property_text(page, "Question"),
                "choice_a": notion_provider.get_property_text(page, "Choice A"),
                "choice_b": notion_provider.get_property_text(page, "Choice B"),
                "choice_c": notion_provider.get_property_text(page, "Choice C"),
                "choice_d": notion_provider.get_property_text(page, "Choice D"),
                "answer": notion_provider.get_property_text(page, "Answer"),
                "explanation": notion_provider.get_property_text(page, "Explanation"),
                "part": notion_provider.get_property_text(page, "Part"),
                "passage": notion_provider.get_property_text(page, "Passage")
            })
        print(json.dumps(results, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Error listing drafts: {e}")

def approve_question(page_id):
    """指定したページIDの問題を Approved に更新する"""
    try:
        notion_provider.update_status(page_id, "Approved")
        print(f"Successfully approved page: {page_id}")
    except Exception as e:
        print(f"Error approving question: {e}")

def main():
    parser = argparse.ArgumentParser(description='Agent-Notion Bridge Utility')
    subparsers = parser.add_subparsers(dest='command')

    # push
    push_parser = subparsers.add_parser('push')
    push_parser.add_argument('json_data', help='Question JSON data string')

    # list-drafts
    subparsers.add_parser('list-drafts')

    # approve
    approve_parser = subparsers.add_parser('approve')
    approve_parser.add_argument('page_id', help='Notion Page ID')

    args = parser.parse_args()

    if args.command == 'push':
        push_question(args.json_data)
    elif args.command == 'list-drafts':
        list_drafts()
    elif args.command == 'approve':
        approve_question(args.page_id)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
