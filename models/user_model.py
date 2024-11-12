users = [
    {'id': 1, 'email': 'admin@admin.com', 'password': 'admin', 'password_changed': False, 'role': 'Administrador'}
]

def get_user(email, password):
    for user in users:
        if user['email'] == email and user['password'] == password:
            return user
    return None

def update_password(user_id, new_password):
    for user in users:
        if user['id'] == user_id:
            user['password'] = new_password
            user['password_changed'] = True
