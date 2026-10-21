class EmptyVectorError(Exception):
    """Error raised if the result of an embed query is empty, it should always contain a float array"""

class VectorDimensionMismatchError(Exception):
    """Error raised if the size of the float array does not match the dimension of the embed model"""
