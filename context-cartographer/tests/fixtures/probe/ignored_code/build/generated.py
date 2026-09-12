def render(readings):
    return "\n".join(reading.reference for reading in readings)
