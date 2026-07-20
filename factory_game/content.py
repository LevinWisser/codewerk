from __future__ import annotations

from factory_game.models import Mission


DIRECTIONS = {"North": (0, -1), "East": (1, 0), "South": (0, 1), "West": (-1, 0)}

ITEM_NAMES = {
    "steel": "Steel",
    "plate": "Plate",
    "gear": "Gear",
    "module": "Gearbox Module",
    "copper": "Copper",
    "polymer": "Polymer",
    "wire": "Wire",
    "housing": "Housing",
    "actuator": "Actuator",
}

MACHINE_DEFINITIONS = {
    "press": ("Press", ["steel"], "plate", 3),
    "mill": ("Mill", ["plate"], "gear", 4),
    "assembly": ("Assembly", ["plate", "gear"], "module", 5),
}

FACTORY_MACHINE_DEFINITIONS = {
    "press": {"name": "Press", "inputs": ["steel"], "output": "plate", "duration": 3, "cost": 500},
    "mill": {"name": "Mill", "inputs": ["plate"], "output": "gear", "duration": 4, "cost": 800},
    "wire_drawer": {"name": "Wire Drawer", "inputs": ["copper"], "output": "wire", "duration": 4, "cost": 700},
    "injection": {"name": "Injection Molder", "inputs": ["polymer"], "output": "housing", "duration": 4, "cost": 900},
    "assembly": {"name": "Assembly", "inputs": ["gear", "wire", "housing"], "output": "actuator", "duration": 6, "cost": 1200},
}

RAW_MATERIAL_PRICES = {"steel": 10, "copper": 12, "polymer": 8}

# Base time plus time per requested unit. More complex production chains receive
# substantially more routing and processing time than single-machine products.
CONTRACT_DURATION_RULES = {
    "plate": (100, 22),
    "gear": (120, 40),
    "wire": (110, 32),
    "housing": (110, 32),
    "actuator": (160, 90),
}


def contract_duration(product: str, quantity: int) -> int:
    base, per_item = CONTRACT_DURATION_RULES[product]
    return base + per_item * quantity

MISSIONS = [
    Mission("boot", "01  System Start", "The maintenance drone is responding again. Move it two tiles east.", "Commands run from top to bottom.", "Reach position (3, 1).", "move(East)\nmove(East)\n", ["move", "directions"], {"position": [3, 1]}, 100),
    Mission("delivery", "02  First Delivery", "Pick up steel at the input warehouse and take it to shipping.", "The drone can carry exactly one item.", "Deliver 1 steel.", "move(South)\npick_up()\n# Move to shipping\n", ["move", "directions", "pick_up", "drop"], {"delivered": {"steel": 1}}, 150),
    Mission("series", "03  Small Batch", "The customer needs three units of steel. A loop avoids repeated code.", "for repeats an indented block.", "Deliver 3 steel.", "for cycle in range(3):\n    # Input warehouse: (1, 2), shipping: (6, 6)\n    pass\n", ["move", "directions", "pick_up", "drop", "loops", "position"], {"delivered": {"steel": 3}}, 220),
    Mission("press", "04  The Press", "Process steel in the press and ship the finished plate.", "drop() transfers an item to a machine; pick_up() collects its finished output.", "Deliver 1 plate.", "# Press: (3, 2)\n# Load it with drop(), start it, and collect the result with pick_up().\n", ["move", "directions", "pick_up", "drop", "machine", "press_machine", "start_machine", "wait"], {"delivered": {"plate": 1}}, 300),
    Mission("sensors", "05  Machine Feedback", "Produce two plates. Query the machine state instead of guessing a fixed wait time.", "while loops and sensors make programs robust.", "Deliver 2 plates.", "# Example:\n# while not machine_is_done():\n#     wait()\n", ["move", "directions", "pick_up", "drop", "machine", "press_machine", "start_machine", "wait", "conditions", "machine_is_done"], {"delivered": {"plate": 2}}, 400),
    Mission("coordinates", "06  Navigation", "Use the current position to deliver steel regardless of the starting point.", "Coordinates start at (0, 0) in the top-left corner.", "Deliver 1 steel and use get_position().", "x, y = get_position()\n# Navigate to the input warehouse at (1, 2) from any position.\n", ["move", "directions", "pick_up", "drop", "position", "conditions", "loops"], {"delivered": {"steel": 1}, "requires_call": "get_position"}, 450),
    Mission("milling", "07  Precision Part", "Press a plate, mill it into a gear, and ship it.", "The output of one machine becomes the input of the next.", "Deliver 1 gear.", "# Press: (3, 2), mill: (5, 2)\n", ["move", "directions", "pick_up", "drop", "machine", "press_machine", "mill_machine", "start_machine", "wait", "machine_is_done", "functions"], {"delivered": {"gear": 1}}, 600),
    Mission("final", "08  Production Cell", "Build a gearbox module from one plate and one gear.", "A good function encapsulates navigation or machine operation.", "Deliver 1 gearbox module.", "def go_to(target_x, target_y):\n    # Implement reusable navigation.\n    pass\n\n# Assembly: (4, 4)\n", ["all"], {"delivered": {"module": 1}}, 1000),
]

HELP = {
    "move": ("move(direction)", "Moves the drone by one tile. A blocked move raises an error.", "move(East)\nmove(South)"),
    "directions": ("Directions", "North, East, South, and West are predefined constants.", "for _ in range(3):\n    move(West)"),
    "pick_up": ("pick_up(item=None)", "In tutorials, picks up the available material. In the main factory, pick_up(item) selects a raw material at the input warehouse; use pick_up() without an argument at a machine output.", "pick_up('steel')  # Input warehouse\npick_up()         # Machine output"),
    "drop": ("drop()", "Transfers the carried item based on context: it loads a machine or stores the item in the unlimited shipping warehouse.", "# Stand on a machine or shipping tile\ndrop()"),
    "discard_item": ("discard_item()", "Discards the item currently carried by the drone and consumes one tick. Calling it with an empty inventory raises an error.", "if get_inventory() is not None:\n    discard_item()"),
    "position": ("get_position()", "Returns the current position as (x, y).", "x, y = get_position()\nwhile x < 5:\n    move(East)\n    x, y = get_position()"),
    "loops": ("Loops", "for repeats a known number of times; while repeats as long as its condition is true.", "for _ in range(4):\n    move(East)"),
    "conditions": ("Conditions", "if runs code only when its condition is true.", "if can_move(East):\n    move(East)"),
    "functions": ("Functions", "def groups reusable steps under a name.", "def step_right():\n    move(East)\n\nstep_right()"),
    "machine": ("Operating Machines", "Stand on a machine, load it with drop(), start it with start_machine(), and collect the finished product with pick_up(). Sensor queries are safer than assumed wait times.", "drop()\nstart_machine()\nwhile not machine_is_done():\n    wait()\npick_up()"),
    "press_machine": ("Press", "Position: (3, 2). Input: 1 steel. Output: 1 plate. Processing time: 3 ticks after start_machine(), so wait(3).", "drop()\nstart_machine()\nwait(3)\npick_up()"),
    "mill_machine": ("Mill", "Position: (5, 2). Input: 1 plate. Output: 1 gear. Processing time: 4 ticks after start_machine(), so wait(4).", "drop()\nstart_machine()\nwait(4)\npick_up()"),
    "assembly_machine": ("Assembly", "Position: (4, 4). Inputs: 1 plate and 1 gear. Output: 1 gearbox module. Processing time: 5 ticks after start_machine(), so wait(5). Load both items one at a time with drop().", "drop()  # First item\n# Fetch the second item\ndrop()\nstart_machine()\nwait(5)\npick_up()"),
    "start_machine": ("start_machine()", "Starts the fully loaded machine on the current tile. Its required tick count is listed in the corresponding machine help entry.", "start_machine()"),
    "machine_is_done": ("machine_is_done()", "Returns True when the machine has a finished product ready.", "while not machine_is_done():\n    wait()"),
    "wait": ("wait(ticks=1)", "Advances simulation ticks so machines can operate.", "wait(3)"),
    "all": ("API Overview", "The final tutorial unlocks every command introduced so far.", "x, y = get_position()"),
    "files": ("Files and Imports", "Add Python files with +. main.py is the entry point. Local modules support normal imports and from module import *; external packages remain blocked.", "# positions.py\nPRESS = (3, 2)\n\n# main.py\nfrom positions import *\nget_to_pos(PRESS)"),
    "contracts": ("Requests and Orders", "get_requests() returns up to eight open offers. After accept_request(id), the contract appears in get_orders(). ticks_left shows the remaining bonus deadline. Complex products receive longer deadlines for their additional production steps. Requests remain until accepted or rejected; active orders can be cancelled with cancel_order(id).", "for request_id, request in get_requests().items():\n    if request['base_payout'] > 100:\n        accept_request(request_id)"),
    "get_requests": ("get_requests()", "Returns a dictionary snapshot of all open requests indexed by request ID. Each entry includes product, quantity, base_payout, on_time_bonus, and duration.", "requests = get_requests()"),
    "get_orders": ("get_orders()", "Returns all active orders. ticks_left is recalculated on every query and reaches zero when late.", "orders = get_orders()"),
    "accept_request": ("accept_request(request_id)", "Accepts an open request, starts its bonus deadline, and consumes one tick.", "accept_request('REQ-0001')"),
    "reject_request": ("reject_request(request_id)", "Rejects an open request. A replacement appears after a short tick delay.", "reject_request('REQ-0001')"),
    "cancel_order": ("cancel_order(order_id)", "Cancels an accepted order without a penalty and consumes one tick. Produced items remain unchanged; a new request appears after a short delay.", "cancel_order('ORD-0001')"),
    "buy": ("buy(item)", "Buys exactly one raw material, deducts its price, and adds it to the input warehouse after one tick. Valid items are steel, copper, and polymer.", "while get_input_stock('steel') < 5:\n    buy('steel')"),
    "get_credits": ("get_credits()", "Returns the currently available credits without consuming a tick.", "if get_credits() >= 10:\n    buy('steel')"),
    "stocks": ("Inventory", "get_input_stock() and get_shipping_stock() return dictionaries. With an item argument, they return that item's quantity directly. Use pick_up(item) at the input warehouse.", "steel_count = get_input_stock('steel')\nall_products = get_shipping_stock()"),
    "get_input_stock": ("get_input_stock(item=None)", "Without an argument: a dictionary snapshot of input stock. With an item: the available quantity of that raw material.", "steel = get_input_stock('steel')"),
    "get_shipping_stock": ("get_shipping_stock(item=None)", "Without an argument: a dictionary snapshot of shipping stock. With an item: the available quantity of that product.", "plates = get_shipping_stock('plate')"),
    "shipping": ("Shipping Orders", "ship(order_id) works only on the shipping tile and only as a complete delivery. If products are missing, the stock and order remain unchanged.", "orders = get_orders()\nfor order_id in orders:\n    ship(order_id)"),
    "ship": ("ship(order_id)", "Ships the selected order in full from the shipping tile. Returns the actual payout and consumes one tick.", "payout = ship('ORD-0001')"),
    "get_tick": ("get_tick()", "Returns the current global factory tick without consuming one.", "now = get_tick()"),
    "building": ("Build Mode", "Build mode pauses running code. Empty, stopped machines can be moved for free or sold for 75 percent of their purchase price. Loaded or running machines are locked.", "# Select BUILD in the top toolbar"),
    "factory_press": ("Buy a Press", "Cost: 500 credits. Input: steel. Output: plate. Duration: 3 ticks.", "buy('steel')"),
    "factory_mill": ("Buy a Mill", "Cost: 800 credits. Input: plate. Output: gear. Duration: 4 ticks.", "# Unlocks after two completed orders"),
    "factory_wire": ("Buy a Wire Drawer", "Cost: 700 credits. Input: copper. Output: wire. Duration: 4 ticks.", "buy('copper')"),
    "factory_injection": ("Buy an Injection Molder", "Cost: 900 credits. Input: polymer. Output: housing. Duration: 4 ticks.", "buy('polymer')"),
    "factory_assembly": ("Actuator Assembly", "Cost: 1200 credits. Inputs: gear, wire, and housing. Output: actuator. Duration: 6 ticks.", "# Load all three items one at a time with drop()"),
}
