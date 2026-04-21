import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import '../models/models.dart';
import '../services/api_service.dart';

enum EditorTool { select, connect, deleteEdge }

enum AppMode { engineering, showcase }

class LayoutProvider with ChangeNotifier {
  final List<LayoutNode> _nodes = [];
  final List<LayoutEdge> _edges = [];
  Map<String, Map<String, dynamic>> _catalogDefaults = {};
  bool _isModifying = false;
  bool _isSyncing = false;
  bool _pendingForceRefresh = false;
  DateTime? _lastModTime;
  DateTime? _lastSyncTime;

  bool get isSyncing =>
      _isModifying ||
      (_lastModTime != null &&
          DateTime.now().difference(_lastModTime!) <
              const Duration(seconds: 2));

  String? _selectedNodeId;
  Set<String> _selectedNodeIds = {};
  Rect? _selectionRect;

  // History for Undo
  final List<LayoutNode> _trashNodes = [];
  final List<LayoutEdge> _trashEdges = [];

  // Advanced Tool State
  EditorTool _currentTool = EditorTool.select;
  String? _connectSourceNodeId;
  Offset? _mousePosition;
  bool _heatmapMode = false;
  bool _isDarkMode = false;
  bool _isometricMode = false;
  AppMode _activeMode = AppMode.showcase;

  Set<String> _highlightedEdges = {};
  Set<String> _candidateEdges = {};
  String? _activePathId;
  String? _focusNodeId;
  int _focusRequestId = 0;
  int _fitRequestId = 0;

  final _uuid = const Uuid();
  final ApiService _apiService = ApiService();

  List<LayoutNode> get nodes => _nodes;
  List<LayoutEdge> get edges => _edges;
  String? get selectedNodeId => _selectedNodeId;
  Set<String> get selectedNodeIds => _selectedNodeIds;
  Rect? get selectionRect => _selectionRect;
  EditorTool get currentTool => _currentTool;
  String? get connectSourceNodeId => _connectSourceNodeId;
  Offset? get mousePosition => _mousePosition;
  bool get heatmapMode => _heatmapMode;
  bool get isDarkMode => _isDarkMode;
  bool get isometricMode => _isometricMode;
  AppMode get activeMode => _activeMode;

  void setAppMode(AppMode mode) {
    if (_activeMode == mode) return;
    _activeMode = mode;
    if (mode == AppMode.engineering) {
      clearLayout();
    } else {
      refreshLayout(force: true);
    }
    notifyListeners();
  }

  Set<String> get highlightedEdges => _highlightedEdges;
  Set<String> get candidateEdges => _candidateEdges;
  String? get activePathId => _activePathId;
  String? get focusNodeId => _focusNodeId;
  int get focusRequestId => _focusRequestId;
  int get fitRequestId => _fitRequestId;

  void requestFitToCanvas() {
    _fitRequestId += 1;
    notifyListeners();
  }

  void toggleHeatmap() {
    _heatmapMode = !_heatmapMode;
    notifyListeners();
  }

  void toggleDarkMode() {
    _isDarkMode = !_isDarkMode;
    notifyListeners();
  }

  void toggleIsometric() {
    _isometricMode = !_isometricMode;
    requestFitToCanvas();
    notifyListeners();
  }

  void setHighlightedEdges(Set<String> edgeIds) {
    _highlightedEdges = edgeIds;
    notifyListeners();
  }

  void setActivePath(String? edgeId) {
    _activePathId = edgeId;
    notifyListeners();
    // Clear active path after a delay for visual effect
    if (edgeId != null) {
      Future.delayed(const Duration(milliseconds: 1500), () {
        if (_activePathId == edgeId) {
          _activePathId = null;
          notifyListeners();
        }
      });
    }
  }

  void setNodes(List<LayoutNode> nodes) {
    _nodes.clear();
    _nodes.addAll(nodes);
    notifyListeners();
  }

  void setEdges(List<LayoutEdge> edges) {
    _edges.clear();
    _edges.addAll(edges);
    notifyListeners();
  }

  LayoutNode? get selectedNode {
    if (_selectedNodeId == null || _nodes.isEmpty) return null;
    final idx = _nodes.indexWhere((n) => n.id == _selectedNodeId);
    return idx != -1 ? _nodes[idx] : null;
  }

  double snapToGrid(double value) => (value / 20).round() * 20.0;

  Future<void> initializeCatalog() async {
    final catalog = await _apiService.getCatalog();
    if (catalog != null) {
      for (var item in catalog) {
        _catalogDefaults[item['type']] = Map<String, dynamic>.from(
          item['defaults'] ?? {},
        );
      }
      notifyListeners();
    }
  }

  void setTool(EditorTool tool) {
    _currentTool = tool;
    _connectSourceNodeId = null;
    notifyListeners();
  }

  void cancelProcess() {
    _currentTool = EditorTool.select;
    _connectSourceNodeId = null;
    _selectedNodeIds.clear();
    notifyListeners();
  }

  void selectAll() {
    _selectedNodeIds = _nodes.map((n) => n.id).toSet();
    notifyListeners();
  }

  void updateMousePosition(Offset pos) {
    if (_currentTool == EditorTool.connect && _connectSourceNodeId != null) {
      _mousePosition = pos;
      notifyListeners();
    }
  }

  void handleNodeClick(String nodeId) {
    if (_currentTool == EditorTool.connect) {
      if (_connectSourceNodeId == null) {
        _connectSourceNodeId = nodeId;
      } else if (_connectSourceNodeId != nodeId) {
        addEdge(_connectSourceNodeId!, nodeId);
        _connectSourceNodeId = nodeId;
      }
      notifyListeners();
      return;
    }
    selectNode(nodeId);
  }

  void selectNode(String? id, {bool multi = false}) {
    if (_currentTool != EditorTool.select && id != null) return;
    if (multi && id != null) {
      if (_selectedNodeIds.contains(id)) {
        _selectedNodeIds.remove(id);
      } else {
        _selectedNodeIds.add(id);
      }
    } else {
      _selectedNodeIds = id != null ? {id} : {};
      _selectedNodeId = id;
    }
    notifyListeners();
  }

  void highlightEdge(
    String edgeId, {
    bool isActive = false,
    bool isCandidate = false,
  }) {
    if (isActive) {
      _activePathId = edgeId;
    } else if (isCandidate) {
      _candidateEdges.add(edgeId);
    } else {
      _highlightedEdges.add(edgeId);
    }
    notifyListeners();
  }

  void clearRoutingUI() {
    _activePathId = null;
    _candidateEdges.clear();
    _highlightedEdges.clear();
    notifyListeners();
  }

  void focusOnNode(String nodeId) {
    if (!_nodes.any((n) => n.id == nodeId)) {
      return;
    }
    _focusNodeId = nodeId;
    _focusRequestId += 1;
    _selectedNodeIds = {nodeId};
    _selectedNodeId = nodeId;
    notifyListeners();
  }

  void pulseConveyorGlow({
    Duration duration = const Duration(milliseconds: 1400),
  }) {
    _highlightedEdges = _edges
        .map((edge) => '${edge.fromNode}_to_${edge.toNode}')
        .toSet();
    notifyListeners();
    Future.delayed(duration, () {
      _highlightedEdges.clear();
      notifyListeners();
    });
  }

  Future<void> addNode(LayoutNodeType type, Offset position) async {
    final snappedX = snapToGrid(position.dx);
    final snappedY = snapToGrid(position.dy);
    final newNode = LayoutNode(
      id: '${type.value.toLowerCase()}-${_uuid.v4().substring(0, 4)}',
      type: type,
      position: LayoutPosition(x: snappedX, y: snappedY),
      properties: Map<String, dynamic>.from(_catalogDefaults[type.value] ?? {}),
    );
    _isModifying = true;
    _nodes.add(newNode);
    _selectedNodeId = newNode.id;
    _selectedNodeIds = {newNode.id};
    notifyListeners();

    final response = await _apiService.addNode(newNode);
    if (!response.success) {
      // Revert if failed
      _nodes.remove(newNode);
      notifyListeners();
    }
    _isModifying = false;
    _lastModTime = DateTime.now();
    notifyListeners();
  }

  Future<void> updateNodePosition(
    String id,
    Offset delta, {
    bool isFinal = false,
  }) async {
    if (_currentTool != EditorTool.select) return;
    final index = _nodes.indexWhere((n) => n.id == id);
    if (index != -1) {
      final node = _nodes[index];
      var newX = node.position.x + delta.dx;
      var newY = node.position.y + delta.dy;
      if (isFinal) {
        newX = snapToGrid(newX);
        newY = snapToGrid(newY);
      }
      final originalNode = node;
      final updatedNode = node.copyWith(
        position: LayoutPosition(x: newX, y: newY),
      );
      _nodes[index] = updatedNode;
      notifyListeners();
      if (isFinal) {
        final response = await _apiService.updateNode(updatedNode);
        if (!response.success) {
          // ROLLBACK
          final currentIdx = _nodes.indexWhere((n) => n.id == id);
          if (currentIdx != -1) {
            _nodes[currentIdx] = originalNode;
            notifyListeners();
          }
        }
        _lastModTime = DateTime.now();
        notifyListeners();
      }
    }
  }

  Future<void> updateNodeProperties(
    String id,
    Map<String, dynamic> properties,
  ) async {
    final index = _nodes.indexWhere((n) => n.id == id);
    if (index != -1) {
      final originalNode = _nodes[index];
      final updatedNode = originalNode.copyWith(properties: properties);
      _nodes[index] = updatedNode;
      notifyListeners();

      final response = await _apiService.updateNode(updatedNode);
      if (!response.success) {
        // ROLLBACK
        final currentIdx = _nodes.indexWhere((n) => n.id == id);
        if (currentIdx != -1) {
          _nodes[currentIdx] = originalNode;
          notifyListeners();
        }
      }
      _lastModTime = DateTime.now();
      notifyListeners();
    }
  }

  Future<void> addEdge(String fromId, String toId) async {
    if (_edges.any((e) => e.fromNode == fromId && e.toNode == toId)) return;
    if (fromId == toId) return;
    final newEdge = LayoutEdge(
      fromNode: fromId,
      toNode: toId,
      transportTime: 0.5,
      properties: {'capacity': 1, 'directionality': 'forward'},
    );
    _edges.add(newEdge);
    notifyListeners();
    try {
      final response = await _apiService.addEdge(newEdge);
      if (!response.success) {
        _edges.remove(newEdge);
        notifyListeners();
      }
    } catch (e) {
      _edges.remove(newEdge);
      notifyListeners();
    }
    _lastModTime = DateTime.now();
    notifyListeners();
  }

  Future<void> bulkDeleteSelected() async {
    if (_selectedNodeIds.isEmpty) return;
    _trashNodes.clear();
    _trashEdges.clear();

    _isModifying = true;
    try {
      final idsToRemove = Set<String>.from(_selectedNodeIds);
      _selectedNodeIds.clear();
      _selectedNodeId = null;

      final deleteFutures = <Future>[];
      for (var id in idsToRemove) {
        final nodeIdx = _nodes.indexWhere((n) => n.id == id);
        if (nodeIdx == -1) continue;

        final node = _nodes[nodeIdx];
        _trashNodes.add(node);
        _trashEdges.addAll(
          _edges.where((e) => e.fromNode == id || e.toNode == id),
        );

        _edges.removeWhere((e) => e.fromNode == id || e.toNode == id);
        _nodes.removeWhere((n) => n.id == id);
        deleteFutures.add(_apiService.deleteNode(id));
      }

      notifyListeners();
      await Future.wait(deleteFutures);
      // If any failed, we might need a refresh to be sure, but for now we simple-revert
      // This is a complex case; we rely on refreshLayout() triggered by time or manual
    } catch (e) {
      // In deep failure, we force-refresh from source of truth
      await refreshLayout(force: true);
    } finally {
      _isModifying = false;
      _lastModTime = DateTime.now();
      notifyListeners();
    }
  }

  Future<void> clearLayout() async {
    _isModifying = true;
    _selectedNodeIds.clear();
    _selectedNodeId = null;

    final deleteFutures = _nodes
        .map((n) => _apiService.deleteNode(n.id))
        .toList();
    _nodes.clear();
    _edges.clear();
    notifyListeners();

    await Future.wait(deleteFutures);
    _isModifying = false;
    _lastModTime = DateTime.now();
    notifyListeners();
    await refreshLayout(force: true);
  }

  Future<void> undoDelete() async {
    if (_trashNodes.isEmpty) return;
    for (var node in _trashNodes) {
      _nodes.add(node);
      await _apiService.addNode(node);
    }
    for (var edge in _trashEdges) {
      if (!_edges.any(
        (e) => e.fromNode == edge.fromNode && e.toNode == edge.toNode,
      )) {
        _edges.add(edge);
        await _apiService.addEdge(edge);
      }
    }
    _trashNodes.clear();
    _trashEdges.clear();
    _lastModTime = DateTime.now();
    notifyListeners();
  }

  Future<void> deleteEdge(String fromNode, String toNode) async {
    final edgeIdx = _edges.indexWhere(
      (e) => e.fromNode == fromNode && e.toNode == toNode,
    );
    if (edgeIdx == -1) return;
    final originalEdge = _edges[edgeIdx];

    _edges.removeAt(edgeIdx);
    notifyListeners();

    try {
      final response = await _apiService.deleteEdge(fromNode, toNode);
      if (!response.success) {
        _edges.insert(edgeIdx, originalEdge);
        notifyListeners();
      }
    } catch (e) {
      _edges.insert(edgeIdx, originalEdge);
      notifyListeners();
    }
    _lastModTime = DateTime.now();
    notifyListeners();
  }

  Future<void> removeSelectedNode() async {
    if (_selectedNodeId == null) return;
    final id = _selectedNodeId!;
    final nodeIdx = _nodes.indexWhere((n) => n.id == id);
    if (nodeIdx == -1) return;
    final node = _nodes[nodeIdx];
    _trashNodes.clear();
    _trashEdges.clear();
    _trashNodes.add(node);
    _trashEdges.addAll(_edges.where((e) => e.fromNode == id || e.toNode == id));
    _edges.removeWhere((e) => e.fromNode == id || e.toNode == id);
    _nodes.removeWhere((n) => n.id == id);
    _selectedNodeId = null;
    _selectedNodeIds.remove(id);
    notifyListeners();
    try {
      final res = await _apiService.deleteNode(id);
      if (!res.success) {
        _nodes.insert(nodeIdx, node);
        _edges.addAll(
          _trashEdges.where((e) => e.fromNode == id || e.toNode == id),
        );
        notifyListeners();
      }
    } catch (e) {
      _nodes.insert(nodeIdx, node);
      _edges.addAll(
        _trashEdges.where((e) => e.fromNode == id || e.toNode == id),
      );
      notifyListeners();
    }
  }

  void startSelectionBox(Offset start) {
    if (_currentTool != EditorTool.select) return;
    _selectionRect = Rect.fromPoints(start, start);
    notifyListeners();
  }

  void updateSelectionBox(Offset current) {
    if (_selectionRect != null) {
      _selectionRect = Rect.fromPoints(_selectionRect!.topLeft, current);
      _updateMultiSelectFromRect();
      notifyListeners();
    }
  }

  void endSelectionBox() {
    _selectionRect = null;
    notifyListeners();
  }

  void _updateMultiSelectFromRect() {
    if (_selectionRect == null) return;
    _selectedNodeIds.clear();
    for (var node in _nodes) {
      final nodeRect = Rect.fromLTWH(node.position.x, node.position.y, 80, 80);
      if (_selectionRect!.overlaps(nodeRect)) {
        _selectedNodeIds.add(node.id);
      }
    }
  }

  Future<void> autoAlignToGrid() async {
    for (int i = 0; i < _nodes.length; i++) {
      final node = _nodes[i];
      final newX = snapToGrid(node.position.x);
      final newY = snapToGrid(node.position.y);
      if (newX != node.position.x || newY != node.position.y) {
        final updated = node.copyWith(
          position: LayoutPosition(x: newX, y: newY),
        );
        _nodes[i] = updated;
        await _apiService.updateNode(updated);
      }
    }
    _lastModTime = DateTime.now();
    notifyListeners();
  }

  Future<void> refreshLayout({bool force = false}) async {
    if (_isModifying || _isSyncing) {
      if (force) {
        _pendingForceRefresh = true;
      }
      return;
    }

    // Strict throttling: Prevent more than 2 syncs per second
    if (!force &&
        _lastSyncTime != null &&
        DateTime.now().difference(_lastSyncTime!).inMilliseconds < 500) {
      return;
    }

    // Cooldown logic to prevent resurrection from backend cache
    if (!force &&
        _lastModTime != null &&
        DateTime.now().difference(_lastModTime!) < const Duration(seconds: 2)) {
      debugPrint('Sync deferred: modification cooldown active');
      return;
    }

    _isSyncing = true;
    try {
      final current = await _apiService.loadLayout();
      if (current != null && !_isModifying) {
        final trashedIds = _trashNodes.map((n) => n.id.toLowerCase()).toSet();

        // IDENTITY SANITIZATION: Filter out nodes that we know should be deleted
        final List<Future> cleanupTasks = [];
        final filteredNodes = current.nodes.where((n) {
          if (trashedIds.contains(n.id.toLowerCase())) {
            debugPrint(
              'REJECTED: Preventing resurrection of trashed node ${n.id}',
            );
            // Re-assert deletion to the server
            cleanupTasks.add(_apiService.deleteNode(n.id));
            return false;
          }
          return true;
        }).toList();

        if (cleanupTasks.isNotEmpty) {
          await Future.wait(cleanupTasks);
        }

        _nodes.clear();
        _nodes.addAll(filteredNodes);
        _edges.clear();
        _edges.addAll(current.edges);

        // Clean selection
        _selectedNodeIds.removeWhere((id) => !_nodes.any((n) => n.id == id));
        _lastSyncTime = DateTime.now();
        _fitRequestId += 1;
        notifyListeners();
      }
    } finally {
      _isSyncing = false;
      if (_pendingForceRefresh) {
        _pendingForceRefresh = false;
        Future.microtask(() => refreshLayout(force: true));
      }
    }
  }
}
