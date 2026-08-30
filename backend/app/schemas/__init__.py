"""Pydantic request/response models.

Response schemas are the API's outbound allow-list: a field that is not
declared here can never reach a client, which is how `password_hash` and
`object_key` stay internal.
"""
