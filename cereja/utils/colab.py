import base64

__all__ = ['ColabMediaOutput']


class ColabMediaOutput:
    ITEM_WIDTH = 254
    ITEM_HEIGHT = 254

    _layout = {
        'item': f"""<div class='col-sm text-center'>
<blockquote class="blockquote">
{{media_content}}
<footer><span>{{caption}}</span></footer>
</blockquote>
</div>""",
        'base': f"""
<script src='https://code.jquery.com/jquery-3.2.1.slim.min.js' integrity='sha384-KJ3o2DKtIkvYIK3UENzmM7KCkRr/rE9/Qpg6aAZGJwFDMVNA/GpGFF93hXpG5KkN' crossorigin='anonymous'></script>
<script src='https://cdn.jsdelivr.net/npm/popper.js@1.12.9/dist/umd/popper.min.js' integrity='sha384-ApNbgh9B+Y1QKtv3Rn7W3mgPxhU9K/ScQsAP7hUibX39j7fakFPskvXusvfa0b4Q' crossorigin='anonymous'></script>
<script src='https://cdn.jsdelivr.net/npm/bootstrap@4.0.0/dist/js/bootstrap.min.js' integrity='sha384-JZR6Spejh4U02d8jOt6vLEHfe/JQGiRRSQQxSfFWpi1MquVdAyjUar5+76PVCmYl' crossorigin='anonymous'></script>
<link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/bootstrap@4.0.0/dist/css/bootstrap.min.css' integrity='sha384-Gn5384xqQ1aoWXA+058RXPxPg6fy4IWvTNh0E263XmFcJlSAwiGgFAW/dAiS6JXm' crossorigin='anonymous'>
<div class='container'>
<div class='row'>
{{content}}
</div>
</div>
<script>
    body = document.getElementsByTagName('body')[0]
    body.classList.add('bg-dark')
</script>
"""
    }

    _types = {
        'video': f"""
<video width='{ITEM_WIDTH}' height='{ITEM_HEIGHT}' alt='\\' controls>
    <source src='data:video/mp4;base64,{{media_content_data}}' type=video/mp4 />
</video>
"""

    }

    def __init__(self):
        try:
            from IPython.display import HTML  # noqa: F821
            self.html = HTML
        except ModuleNotFoundError:
            raise Exception('Use only colab')
        self._base = self._layout['base']
        self._content_data = []

    def add_item(self, type_, data, caption=''):
        from cereja.file import FileIO
        from cereja.system import Path
        assert type_ in self._types, f'Only accepted types {tuple(self._types)}'
        if type_ == 'video':
            if isinstance(data, str):
                data = Path(data)
                assert data.suffix == '.mp4', 'Only accepted mp4 type.'
                data = FileIO.load(data).data

            data = base64.b64encode(data).decode("ascii")
            media_content = self._types[type_].format(media_content_data=data)
            media_content = self._layout['item'].format(media_content=media_content, caption=caption)
            self._content_data.append(media_content)

    def show(self):

        html = self._base.format(content=''.join(self._content_data))
        return self.html(
            data=html
        )
