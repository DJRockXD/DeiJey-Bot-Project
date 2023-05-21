import mouse
import time
import logging

log = logging.getLogger('logger')  # get the main logger


def mouse_location_save_data(request):
    current_mouse_coordinates = mouse.get_position()
    log.debug(f"mouse coordinates: {current_mouse_coordinates}")
    try:
        entry_name = request.split(' as ')[1]
        log.debug(f'New entry name acquired from user: {entry_name}')

        data_string = f'{entry_name}@{current_mouse_coordinates}'
        return data_string

    except IndexError:
        log.exception("Syntax problem: the entry that is meant to be saved is the one specified after the word 'as'.")
        return None


def mouse_location_get_entry(request):
    if " to " in request:
        sorted_request = request.split(" to ")
    elif " the " in request:
        sorted_request = request.split(" the ")
    else:
        sorted_request = request.replace("fast travel ", "")

    log.debug(f"sorted request for mouse travel: {sorted_request}")
    try:
        if isinstance(sorted_request, list):
            log.debug(f'Fast travel entry extracted from request: {sorted_request[1]}')
            return sorted_request[1]
        else:
            log.debug(f'Fast travel entry extracted from request: {sorted_request}')
            return sorted_request

    except IndexError:
        log.exception("Syntax problem: the entry that is traveled to is the one specified after the word 'to'.",
                      exc_info=False)
        return None


def mouse_location_travel(coordinates, entry):
    if coordinates:
        coordinates = coordinates.replace("(", "").replace(")", "").split(", ")

        mouse.move(coordinates[0], coordinates[1], absolute=True, duration=0.1)
        log.info(f'fast traveled to {entry}')


def mouse_movement(request):
    num = 0
    for i in reversed(range(1, 2000)):
        if f"{i}" in request and ("down" in request or "right" in request):
            num = i
            break
        elif f"{i}" in request and ("up" in request or "off" in request or "left" in request):
            num = -i
            break

    if "up" in request or "off" in request or "down" in request:
        mouse.move(0, num, absolute=False, duration=0.1)
        time.sleep(0.1)
        log.info(f"Moved {num} units on the y axis.")

    elif "right" in request or "left" in request:
        mouse.move(num, 0, absolute=False, duration=0.1)
        time.sleep(0.1)
        log.info(f"Moved {num} units on the x axis.")


def mouse_click(request):
    if 'double' in request and 'click' in request:
        mouse.double_click('left')
        log.info('double-left clicked')
        time.sleep(1)
    elif 'double' in request and 'right' in request:
        mouse.double_click('right')
        log.info('double-right clicked')
        time.sleep(1)

    elif 'right' in request:
        mouse.click('right')
        log.info("right clicked")
        time.sleep(1)
    else:
        mouse.click('left')
        log.info("left clicked")
        time.sleep(1)


def mouse_scroll(request):
    for i in reversed(range(1, 100)):
        if f'{i}' in request:
            if 'up' in request:
                mouse.wheel(5)

            elif 'down' in request:
                mouse.wheel(-5)
