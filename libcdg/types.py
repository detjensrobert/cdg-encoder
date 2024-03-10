from typing import Annotated, Literal, TypeVar
import numpy as np
import numpy.typing as npt

# from .constants import *
# cant use constants in Literal >:(((

Block = Annotated[npt.NDArray, Literal[12, 6]]
DisplayFrame = Annotated[Block, Literal[16, 48]]
FullFrame = Annotated[Block, Literal[18, 50]]
