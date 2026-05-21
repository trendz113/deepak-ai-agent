def run_agent():
    tasks = get_tasks()

    prompt = f"""
    You are Deepak AI worker.

    Current tasks:
    {tasks}

    Do:
    1. Create one useful new task
    2. Decide one task to complete
    3. If task involves writing or research → generate actual content

    Format:
    NEW_TASK: ...
    COMPLETE_TASK_ID: ...
    ACTION: ...
    OUTPUT_FILE: filename.txt (only if writing content)
    CONTENT: actual content (only if needed)
    """

    result = think(prompt)

    # 🔹 Save new task
    if "NEW_TASK:" in result:
        task = result.split("NEW_TASK:")[1].split("\n")[0].strip()
        add_task(task)

    # 🔹 Complete task
    if "COMPLETE_TASK_ID:" in result:
        try:
            task_id = int(result.split("COMPLETE_TASK_ID:")[1].split("\n")[0].strip())
            complete_task(task_id)
        except:
            pass

    # 🔥 NEW: File execution
    if "OUTPUT_FILE:" in result and "CONTENT:" in result:
        try:
            filename = result.split("OUTPUT_FILE:")[1].split("\n")[0].strip()
            content = result.split("CONTENT:")[1].strip()

            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)

            print(f"✅ File created: {filename}")

        except Exception as e:
            print("File error:", e)

    return result
