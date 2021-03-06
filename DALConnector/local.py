import re

def propername(name):
    name = name.upper()

    if name.isdecimal():
        return name.zfill(3)

    nums = re.search(r'^(\d+)([A-Z]*)$', name, re.IGNORECASE)
    if not nums:
        return None
    else:
        return f'{nums[1].zfill(3)}{nums[2]}'

def displayname(name):
    if name is None:
        return ''

    return re.sub(r'^0{1,2}', '', name)

