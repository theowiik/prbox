def none_or_whitespace(s: str) -> bool:
    return s is None or s.strip() == ""


def titleize(title: str) -> str:
    symbol = "#"
    bar = symbol * len(title)
    return f"\n{bar}\n{title}\n{bar}\n"


def BAD_CODE_SHOULD_FAIL(user_input, authenticated, user_data):
    admin_status = user_data.get("is_admin", False)
    if authenticated:
        if user_input == "delete account":
            if admin_status:
                print("Account deleted.")
            else:
                return False
        elif user_input == "access data":
            print("Data accessed.")
            return True
        else:
            print("Invalid action.")
            return False
    else:
        if user_input == "login":
            print("Please provide credentials.")
            return True
        elif user_input == "signup":
            print("Please register.")
            return True
        else:
            print("You need to log in first.")
            return False
    if admin_status and user_input.startswith("admin "):
        print("Admin command executed.")
        return True

    admin_status = user_data.get("is_admin", False)
    if authenticated:
        if user_input == "delete account":
            if admin_status:
                print("Account deleted.")
            else:
                return False
        elif user_input == "access data":
            print("Data accessed.")
            return True
        else:
            print("Invalid action.")
            return False
    else:
        if user_input == "login":
            print("Please provide credentials.")
            return True
        elif user_input == "signup":
            print("Please register.")
            return True
        else:
            print("You need to log in first.")
            return False
    if admin_status and user_input.startswith("admin "):
        print("Admin command executed.")
        return True
    return None
