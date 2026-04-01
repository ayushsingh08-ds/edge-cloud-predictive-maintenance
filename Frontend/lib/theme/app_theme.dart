import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  // Tactile Sanctuary Palette
  static const Color sageGreen = Color(0xFF8BA88E);
  static const Color darkSage = Color(0xFF5F7464);
  static const Color creamBackground = Color(0xFFFDFBF7);
  static const Color surfaceLayer = Color(0xFFF5F2EB);
  static const Color softShadow = Color(0xFFE0E5EC);
  static const Color textMain = Color(0xFF2D3436);
  static const Color textMuted = Color(0xFF636E72);

  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: sageGreen,
        primary: sageGreen,
        background: creamBackground,
        surface: creamBackground,
      ),
      scaffoldBackgroundColor: creamBackground,
      textTheme: GoogleFonts.beVietnamProTextTheme(),
    );
  }

  // Claymorphism Decoration
  static BoxDecoration clayDecoration() {
    return BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(32),
      boxShadow: [
        BoxShadow(
          color: Colors.white.withOpacity(0.8),
          offset: const Offset(-10, -10),
          blurRadius: 20,
        ),
        BoxShadow(
          color: const Color(0xFFD1D9E6),
          offset: const Offset(10, 10),
          blurRadius: 20,
        ),
      ],
    );
  }
}
