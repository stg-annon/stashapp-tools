# stashapp-tools
This library primarily serves as a API wrapper for [Stash](https://github.com/stashapp/stash) written in python

### Usage
```python
import stashapi.log as log
from stashapi.stashapp import StashInterface

stash = StashInterface({
    "scheme": "http",
    "domain":"localhost",
    "port": "9999",
    "logger": log
})

scene_data = stash.find_scene(1234)
log.info(scene_data)
```
This example creates a connection to Stash query's a scene with ID 1234 and prints the result to Stash's logs