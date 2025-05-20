class SystemConfiguration:
    _ui_hints = {}
    _ui_cats = {'gen': 'General',}
    dummy: str = "dummy"
    _ui_hints["dummy"] = {'name': 'Dymmy Variable', 'category': _ui_cats['gen']}