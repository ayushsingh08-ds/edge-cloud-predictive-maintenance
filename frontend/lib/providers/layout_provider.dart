import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import '../models/models.dart';
import '../services/api_service.dart';

enum EditorTool { select, connect, deleteEdge }

class LayoutProvider with ChangeNotifier {
  final List<LayoutNode> _nodes = [];
  final List<LayoutEdge> _edges = [];
  Map<String, Map<String, dynamic>> _catalogDefaults = {};
  
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

  LayoutNode? get selectedNode => _selectedNodeId != null
      ? _nodes.firstWhere((n) => n.id == _selectedNodeId, orElse: () => _nodes.first)
      : null;

  double snapToGrid(double value) => (value / 20).round() * 20.0;

  Future<void> initializeCatalog() async {
    final catalog = await _apiService.getCatalog();
    if (catalog != null) {
      for (var item in catalog) {
        _catalogDefaults[item['type']] = Map<String, dynamic>.from(item['defaults'] ?? {});
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

  Future<void> addNode(LayoutNodeType type, Offset position) async {
    final snappedX = snapToGrid(position.dx);
    final snappedY = snapToGrid(position.dy);
    final newNode = LayoutNode(
      id: '${type.value.toLowerCase()}-${_uuid.v4().substring(0, 4)}',
      type: type,
      position: LayoutPosition(x: snappedX, y: snappedY),
      properties: Map<String, dynamic>.from(_catalogDefaults[type.value] ?? {}),
    );
    _nodes.add(newNode);
    _selectedNodeId = newNode.id;
    _selectedNodeIds = {newNode.id};
    notifyListeners();
    await _apiService.addNode(newNode);
  }

  Future<void> updateNodePosition(String id, Offset delta, {bool isFinal = false}) async {
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
      final updatedNode = node.copyWith(position: LayoutPosition(x: newX, y: newY));
      _nodes[index] = updatedNode;
      notifyListeners();
      if (isFinal) await _apiService.updateNode(updatedNode);
    }
  }

  Future<void> updateNodeProperties(String id, Map<String, dynamic> properties) async {
    final index = _nodes.indexWhere((n) => n.id == id);
    if (index != -1) {
      final updatedNode = _nodes[index].copyWith(properties: properties);
      _nodes[index] = updatedNode;
      notifyListeners();
      await _apiService.updateNode(updatedNode);
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
    await _apiService.addEdge(newEdge);
  }

  Future<void> bulkDeleteSelected() async {
    if (_selectedNodeIds.isEmpty) return;
    _trashNodes.clear();
    _trashEdges.clear();
    final idsToRemove = Set<String>.from(_selectedNodeIds);
    _selectedNodeIds.clear();
    _selectedNodeId = null;
    for (var id in idsToRemove) {
      final node = _nodes.firstWhere((n) => n.id == id);
      _trashNodes.add(node);
      _trashEdges.addAll(_edges.where((e) => e.fromNode == id || e.toNode == id));
      _edges.removeWhere((e) => e.fromNode == id || e.toNode == id);
      _nodes.removeWhere((n) => n.id == id);
      _apiService.deleteNode(id);
    }
    notifyListeners();
  }

  Future<void> undoDelete() async {
    if (_trashNodes.isEmpty) return;
    for (var node in _trashNodes) {
      _nodes.add(node);
      await _apiService.addNode(node);
    }
    for (var edge in _trashEdges) {
      if (!_edges.any((e) => e.fromNode == edge.fromNode && e.toNode == edge.toNode)) {
        _edges.add(edge);
        await _apiService.addEdge(edge);
      }
    }
    _trashNodes.clear();
    _trashEdges.clear();
    notifyListeners();
  }

  Future<void> deleteEdge(String fromNode, String toNode) async {
    final success = await _apiService.deleteEdge(fromNode, toNode);
    if (success) {
      _edges.removeWhere((e) => e.fromNode == fromNode && e.toNode == toNode);
      notifyListeners();
    }
  }

  Future<void> removeSelectedNode() async {
    if (_selectedNodeId == null) return;
    final id = _selectedNodeId!;
    final node = _nodes.firstWhere((n) => n.id == id);
    _trashNodes.clear();
    _trashEdges.clear();
    _trashNodes.add(node);
    _trashEdges.addAll(_edges.where((e) => e.fromNode == id || e.toNode == id));
    _edges.removeWhere((e) => e.fromNode == id || e.toNode == id);
    _nodes.removeWhere((n) => n.id == id);
    _selectedNodeId = null;
    _selectedNodeIds.remove(id);
    notifyListeners();
    await _apiService.deleteNode(id);
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

  Future<void> refreshLayout() async {
    final current = await _apiService.loadLayout();
    if (current != null) {
      _nodes.clear();
      _nodes.addAll(current.nodes);
      _edges.clear();
      _edges.addAll(current.edges);
      notifyListeners();
    }
  }
}
