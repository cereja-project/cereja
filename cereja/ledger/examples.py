"""Finite synthetic fixtures, never adapters for filesystem/network services."""
import time


TEXT = ('Synthetic text/layout example\n\n'
        '# Canonical text\n  Indentation and intentional spaces  \n\tTabbed value\n\n'
        'Unicode: café, e\u0301, 界, 👩\u200d💻\n'
        'Literal hostile controls: \x1b[31m <script> & text\n\n'
        'Select this result with Tab. Ctrl+A selects canonical text.\n'
        'Ctrl+C reports Copy unavailable; no clipboard transport is installed.\n'
        'PageUp/PageDown scroll. F1 opens help; Escape restores the composer.')


def progress(context, steps=20):
    """At most 20 finite in-memory batches, with safe between-batch checkpoints."""
    if type(steps) is not int or not 1 <= steps <= 20:
        raise ValueError('Synthetic steps must be 1..20')
    context.running()
    checksum = 0
    for completed in range(1, steps + 1):
        context.checkpoint()
        # Deliberately paced synthetic work. Counts advance only after a batch.
        for value in range(1000):
            checksum = (checksum + value * completed) % 65521
        time.sleep(.05)
        context.progress(completed, total=steps, reliable_total=True,
                         message='Synthetic batches')
    context.checkpoint()
    return f'Synthetic example completed {steps} batches. Checksum: {checksum}. No files or network used.'
