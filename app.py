"""
AutoPost - Multi-Brand Social Media Generator
A dynamic Streamlit application for generating branded social media images.
"""

import os
import sys
import json
import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps, ImageFont

import streamlit as st


def get_base_path() -> Path:
    """Get the base path for the application (works with PyInstaller)."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return Path(sys._MEIPASS)
    else:
        # Running as script
        return Path(__file__).parent


def scan_template_folders(base_path: Path) -> list[str]:
    """
    Scan the base directory for folders containing 'Template' in the name.
    
    Args:
        base_path: The directory to scan
        
    Returns:
        List of template folder names
    """
    templates = []
    try:
        for item in os.listdir(base_path):
            item_path = base_path / item
            if item_path.is_dir() and "Template" in item:
                templates.append(item)
    except OSError as e:
        st.error(f"Error scanning directory: {e}")
    return sorted(templates)


def load_layout_config(template_path: Path) -> dict | None:
    """
    Load the layout.json configuration from a template folder.
    
    Args:
        template_path: Path to the template folder
        
    Returns:
        Dictionary with layout configuration or None if not found
    """
    layout_file = template_path / "layout.json"
    if not layout_file.exists():
        st.error(f"layout.json not found in {template_path}")
        return None
    
    try:
        with open(layout_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON in layout.json: {e}")
        return None


def get_available_formats(config: dict) -> list[str]:
    """Get list of available formats from config."""
    if "formats" in config:
        return list(config["formats"].keys())
    else:
        # Legacy format - single template
        return ["default"]


def get_format_config(config: dict, format_name: str) -> dict:
    """Get configuration for a specific format."""
    if "formats" in config:
        format_config = config["formats"].get(format_name, {})
        # Merge with global settings
        format_config["font_size"] = config.get("font_size", {})
        format_config["font_color"] = config.get("font_color", "#FFFFFF")
        return format_config
    else:
        # Legacy format
        return config


def load_template_image(template_path: Path, format_config: dict) -> Image.Image | None:
    """
    Load the template background image.
    
    Args:
        template_path: Path to the template folder
        format_config: Format-specific configuration
        
    Returns:
        PIL Image object or None if not found
    """
    template_file = format_config.get("template_file", "1080x1350.png")
    image_path = template_path / template_file
    
    if not image_path.exists():
        st.error(f"Template image '{template_file}' not found in {template_path}")
        return None
    
    try:
        return Image.open(image_path).convert("RGBA")
    except Exception as e:
        st.error(f"Error loading template image: {e}")
        return None


def load_font(template_path: Path, size: int) -> ImageFont.FreeTypeFont:
    """
    Load a custom font from the template folder or fallback to default.
    
    Args:
        template_path: Path to the template folder
        size: Font size in pixels
        
    Returns:
        PIL Font object
    """
    # Try to find a .ttf file in the template folder
    ttf_files = list(template_path.glob("*.ttf"))
    
    if ttf_files:
        try:
            return ImageFont.truetype(str(ttf_files[0]), size)
        except Exception:
            pass
    
    # Try common system fonts
    system_fonts = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/calibri.ttf",
    ]
    
    for font_path in system_fonts:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue
    
    # Fallback to default
    return ImageFont.load_default()


def create_rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    """
    Create a rounded rectangle mask.
    
    Args:
        size: (width, height) of the mask
        radius: Corner radius in pixels
        
    Returns:
        PIL Image mask with rounded corners
    """
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (size[0] - 1, size[1] - 1)], radius=radius, fill=255)
    return mask


def process_photo(photo: Image.Image, slot: dict) -> Image.Image:
    """
    Process a user photo to fit a slot using center-crop.
    
    Args:
        photo: PIL Image of the user's photo
        slot: Slot configuration with x, y, w, h, radius
        
    Returns:
        Processed PIL Image with rounded corners
    """
    width = slot["w"]
    height = slot["h"]
    radius = slot.get("radius", 0)
    
    # Use ImageOps.fit for center-crop resizing with LANCZOS filter
    fitted = ImageOps.fit(photo, (width, height), method=Image.Resampling.LANCZOS)
    
    # Convert to RGBA if needed
    if fitted.mode != "RGBA":
        fitted = fitted.convert("RGBA")
    
    # Apply rounded corners if specified
    if radius > 0:
        mask = create_rounded_mask((width, height), radius)
        # Create transparent background
        result = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        result.paste(fitted, (0, 0), mask)
        return result
    
    return fitted


def composite_images(
    template: Image.Image,
    photos: list[Image.Image],
    slots: list[dict]
) -> Image.Image:
    """
    Composite user photos onto the template at specified slots.
    
    Args:
        template: Background template image
        photos: List of user photos
        slots: List of slot configurations
        
    Returns:
        Composited PIL Image
    """
    result = template.copy()
    
    for i, (photo, slot) in enumerate(zip(photos, slots)):
        processed = process_photo(photo, slot)
        x, y = slot["x"], slot["y"]
        result.paste(processed, (x, y), processed)
    
    return result


def render_text(
    image: Image.Image,
    format_config: dict,
    template_path: Path,
    model: str,
    price: str,
    year: str = "",
    km: str = "",
    plate: str = "",
    vendedor: str = "",
    telefone: str = "",
    unidade: str = "",
    endereco: str = ""
) -> Image.Image:
    """
    Render text onto the image at specified positions.
    First clears placeholder text areas, then draws user text.
    """
    result = image.copy()
    draw = ImageDraw.Draw(result)
    
    text_pos = format_config.get("text_pos", {})
    font_sizes = format_config.get("font_size", {})
    font_color = format_config.get("font_color", "#FFFFFF")
    text_align_right = format_config.get("text_align_right", [])
    
    # Clear placeholder text areas (left and right)
    for area_key in ["text_clear_area_left", "text_clear_area_right"]:
        area = format_config.get(area_key, None)
        if area:
            x1, y1, x2, y2 = area
            draw.rectangle([(x1, y1), (x2, y2)], fill="#1a1a1a")
    
    # Load fonts
    model_font = load_font(template_path, font_sizes.get("modelo", 42))
    price_font = load_font(template_path, font_sizes.get("preco", 28))
    default_font = load_font(template_path, font_sizes.get("default", 22))
    
    def draw_text_field(key, text, font):
        if text and key in text_pos:
            pos = tuple(text_pos[key])
            anchor = "ra" if key in text_align_right else "la"
            draw.text(pos, text, font=font, fill=font_color, anchor=anchor)
    
    # Left side - Vehicle info
    draw_text_field("modelo", model, model_font)
    draw_text_field("preco", price, price_font)
    draw_text_field("ano", year, default_font)
    
    km_text = f"Km {km}" if km and not km.lower().startswith("km") else km
    draw_text_field("km", km_text, default_font)
    
    plate_text = f"Final de placa {plate}" if plate else ""
    draw_text_field("placa", plate_text, default_font)
    
    # Right side - Seller info
    draw_text_field("vendedor", vendedor, default_font)
    draw_text_field("telefone", telefone, default_font)
    draw_text_field("unidade", unidade, default_font)
    draw_text_field("endereco", endereco, default_font)
    
    return result


def image_to_bytes(image: Image.Image, format: str = "PNG") -> bytes:
    """Convert PIL Image to bytes for download."""
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    return buffer.getvalue()


def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="AutoPost - Gerador de Cards",
        page_icon="🚗",
        layout="wide"
    )
    
    st.title("🚗 AutoPost - Gerador de Cards para Redes Sociais")
    
    # Get base path
    base_path = get_base_path()
    
    # Scan for template folders
    templates = scan_template_folders(base_path)
    
    if not templates:
        st.error("Nenhuma pasta de template encontrada. Certifique-se de que existem pastas com 'Template' no nome.")
        return
    
    # Sidebar - Brand Selection
    with st.sidebar:
        st.header("🏷️ Seleção de Marca")
        selected_template = st.selectbox(
            "Escolha a marca:",
            templates,
            format_func=lambda x: x.replace("Template ", "")
        )
        
        # Load configuration
        template_path = base_path / selected_template
        config = load_layout_config(template_path)
        
        if not config:
            return
        
        # Format selector
        available_formats = get_available_formats(config)
        
        st.header("📐 Formato")
        format_labels = {
            "1080x1350": "📱 Instagram Feed (1080x1350)",
            "1080x1080": "⬜ Quadrado (1080x1080)",
            "1080x1920": "📲 Stories (1080x1920)",
            "1080x566": "🖼️ Banner/Capa (1080x566)",
            "default": "📄 Padrão"
        }
        
        selected_format = st.selectbox(
            "Escolha o formato:",
            available_formats,
            format_func=lambda x: format_labels.get(x, x)
        )
        
        st.divider()
        st.caption("📁 Templates encontrados:")
        for t in templates:
            st.caption(f"• {t}")
    
    # Get format-specific config
    format_config = get_format_config(config, selected_format)
    
    # Load template image
    template_image = load_template_image(template_path, format_config)
    
    if not template_image:
        return
    
    # Main area - Form inputs
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📝 Informações do Veículo")
        
        model = st.text_input("Modelo do veículo", placeholder="Ex: Audi RS6 Avant")
        price = st.text_input("Preço", placeholder="Ex: R$ 850.000,00")
        year = st.text_input("Ano", placeholder="Ex: 2023/2024")
        km = st.text_input("Quilometragem", placeholder="Ex: 15.000")
        plate = st.text_input("Final da placa", placeholder="Ex: 5")
        
        st.divider()
        
        st.subheader("👤 Informações do Vendedor")
        
        vendedor = st.text_input("Nome do Vendedor", placeholder="Ex: João Silva")
        
        # Predefined store locations
        LOJAS = {
            "-- Selecione a Unidade --": ("", ""),
            "Bexp Audi Alphaville": (
                "(11) 4196-1011",
                "Alameda Araguaia, 1993 - Alphaville, Barueri"
            ),
            "Bexp Jeep Brooklin": (
                "(11) 5102-5555",
                "Av. Jurubatuba, 33 - Vila Cordeiro, São Paulo"
            ),
            "Bexp Jeep Butantã": (
                "(11) 3723-2099",
                "Av. Corifeu de Azevedo Marques, 152 - Butantã, SP"
            ),
            "Bexp Jeep Morumbi": (
                "(11) 2150-0000",
                "Av. Giovanni Gronchi, 6328 - Vila Andrade, SP"
            ),
            "Duo Porsche": (
                "(11) 4196-1020",
                "Av. Heitor Penteado, 800 - Sumarezinho, SP"
            ),
            "Duo Porsche Alphaville": (
                "(11) 2150-0030",
                "Alameda Araguaia, 2011 - Alphaville, Barueri"
            ),
            "Duo Porsche Vila Leopoldina": (
                "(11) 4196-1030",
                "Av. Dr. Gastão Vidigal - Vila Leopoldina, SP"
            ),
        }
        
        loja_selecionada = st.selectbox(
            "Selecione a Unidade",
            options=list(LOJAS.keys())
        )
        
        # Get predefined values
        telefone_default, endereco_default = LOJAS.get(loja_selecionada, ("", ""))
        unidade = loja_selecionada if loja_selecionada != "-- Selecione a Unidade --" else ""
        
        telefone = st.text_input(
            "Telefone",
            value=telefone_default,
            placeholder="Ex: (11) 99999-9999"
        )
        endereco = st.text_input(
            "Endereço",
            value=endereco_default,
            placeholder="Ex: Av. Paulista, 1000"
        )
        
        st.divider()
        
        st.subheader("📷 Fotos do Veículo")
        slots = format_config.get("slots", [])
        num_slots = len(slots)
        st.caption(f"Faça upload de {num_slots} fotos do veículo")
        
        uploaded_files = st.file_uploader(
            "Selecione as imagens",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            key="photo_uploader"
        )
        
        if uploaded_files:
            st.caption(f"✅ {len(uploaded_files)} foto(s) selecionada(s)")
    
    with col2:
        st.subheader("👁️ Prévia do Template")
        
        # Show template preview
        preview_template = template_image.copy()
        preview_template.thumbnail((400, 600))
        st.image(preview_template, caption=f"Template: {selected_template} - {selected_format}")
    
    st.divider()
    
    # Generate button
    generate_col, download_col = st.columns([1, 1])
    
    with generate_col:
        generate_btn = st.button("🎨 Gerar Card", type="primary", use_container_width=True)
    
    # Process and generate
    if generate_btn:
        if not uploaded_files:
            st.error("Por favor, faça upload de pelo menos uma foto.")
            return
        
        if len(uploaded_files) < num_slots:
            st.warning(f"O template possui {num_slots} slots. Você enviou {len(uploaded_files)} foto(s). As fotos serão repetidas.")
        
        # Load and process photos
        photos = []
        for f in uploaded_files:
            try:
                img = Image.open(f).convert("RGBA")
                photos.append(img)
            except Exception as e:
                st.error(f"Erro ao carregar imagem {f.name}: {e}")
                return
        
        # Repeat photos if needed to fill all slots
        while len(photos) < num_slots:
            photos.append(photos[len(photos) % len(uploaded_files)])
        
        # Composite images
        with st.spinner("Processando imagens..."):
            result = composite_images(template_image, photos[:num_slots], slots)
            
            # Render text
            result = render_text(
                result,
                format_config,
                template_path,
                model=model,
                price=price,
                year=year,
                km=km,
                plate=plate,
                vendedor=vendedor,
                telefone=telefone,
                unidade=unidade,
                endereco=endereco
            )
        
        # Display result
        st.subheader("✨ Resultado")
        st.image(result, caption="Card gerado", use_container_width=True)
        
        # Store in session state for download
        st.session_state["generated_image"] = result
        st.session_state["model_name"] = model or "card"
        st.session_state["selected_format"] = selected_format
    
    # Download button
    with download_col:
        if "generated_image" in st.session_state:
            img_bytes = image_to_bytes(st.session_state["generated_image"])
            model_name = st.session_state.get('model_name', 'card')
            format_name = st.session_state.get('selected_format', '')
            filename = f"{model_name}_{format_name}.png"
            filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
            
            st.download_button(
                label="⬇️ Baixar Card (PNG)",
                data=img_bytes,
                file_name=filename,
                mime="image/png",
                use_container_width=True
            )


if __name__ == "__main__":
    main()
