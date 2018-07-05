# GDNP
(**GD**ML to MC**NP** converter)


**Warning** : _this is a work in progress. See the [Contributing](#contributing)
section._

## Description
The [gdnp.py](gdnp.py) Python script converts a GDML geometry description to an
MCNP card. Usage is as following:
```bash
./gdnp.py FILE.GDML
```
This will dump the result to `stdout`. Optionally, an output file can also be
provided as 2<sup>nd</sup> argument:
```bash
./gdnp.py FILE.GDML MCNP.CARD
```
An example of [converted geometry](examples/volcano.card) is available in the
[examples](examples) folder. The corresponding
[input GDML](examples/volcano.gdml) is also provided.

Note that the script is implemented in bare **Python 2.7**, i.e. **without
dependencies**. However, note also that it was only tested on Linux so far.


## Contributing
Currently, the converter only supports a **limited number of GDML geometries**:
_tube_ (_closed, centered_), _ellipsoid_ and _intersection_. ~~Rotations~~ are
not implemented as well. In addition, the materials data needs to be manually
filled in at the end of the card. Note that the materials index are properly
mapped, though.

Additional geometries can be added by defining a *convert\_gdml\___{{volume}}__*
function, where **{{volume}}** must be substituted by the GDML name of the
volume to convert. This function must return the MCNP bounding surfaces of the
volume as a list of tuples. See for example the *convert\_gdml\_tube* function.
The snippet below illustrates the syntax by converting a GDML centered Orb:
```python
def convert_gdml_orb(volume, placement):
    """Convert a centered GDML orb to MCNP surfaces
    """
    r = volume["r"]
    if (placement[0] != 0) or (placement[1] != 0) or (placement[2] != 0):
        raise NotImplemented("offset orb")
    else:
        return [(-1, "SO", r)]
```
Each line of the returned list corresponds to a bounding surface. Note that
the first item of the surface definition **must** indicate the surface sign
for being inside the volume, see e.g. pages 3 and 4 of the
[MCNP primer](https://www.mne.k-state.edu/~jks/MCNPprmr.pdf).

## License
The [gdnp.py](gdnp.py) utility is under the MIT license. See the provided
[LICENSE](LICENSE) file.
