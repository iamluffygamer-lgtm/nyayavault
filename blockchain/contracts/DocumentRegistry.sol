// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

contract DocumentRegistry {
    struct Anchor {
        string caseId;
        string documentId;
        uint256 version;
        uint256 timestamp;
        address anchoredBy;
    }

    mapping(bytes32 => Anchor) private anchors;

    event HashAnchored(
        bytes32 indexed documentHash,
        string caseId,
        string documentId,
        uint256 version,
        uint256 timestamp
    );

    function anchorHash(
        bytes32 documentHash,
        string calldata caseId,
        string calldata documentId,
        uint256 version
    ) external returns (bool) {
        require(anchors[documentHash].timestamp == 0, "Hash already anchored");

        anchors[documentHash] = Anchor({
            caseId: caseId,
            documentId: documentId,
            version: version,
            timestamp: block.timestamp,
            anchoredBy: msg.sender
        });

        emit HashAnchored(documentHash, caseId, documentId, version, block.timestamp);
        return true;
    }

    function getAnchor(bytes32 documentHash) external view returns (
        string memory caseId,
        string memory documentId,
        uint256 version,
        uint256 timestamp,
        address anchoredBy
    ) {
        Anchor memory a = anchors[documentHash];
        require(a.timestamp != 0, "Hash not anchored");
        return (a.caseId, a.documentId, a.version, a.timestamp, a.anchoredBy);
    }
}
