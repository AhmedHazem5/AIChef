from rag.query_engine import retrieve_recipe_context

question = "How do I make sushi?"

context = retrieve_recipe_context(question)

print("=" * 80)

if context:
    print(context)
else:
    print("No recipe found.")

print("=" * 80)