__author__ = 'Pablo Ramos Criado'
__students__ = 'Pablo Martín Martín & Hugo Cobos Gutierrez'


from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import time
from typing import Generator, Any, Self
from geojson import Point
import pymongo
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
import yaml

def getLocationPoint(address: str) -> Point:
    """ 
    Obtiene las coordenadas de una dirección en formato geojson.Point
    Utilizar la API de geopy para obtener las coordenadas de la direccion
    Cuidado, la API es publica tiene limite de peticiones, utilizar sleeps.

    Parameters
    ----------
        address : str
            direccion completa de la que obtener las coordenadas
    Returns
    -------
        geojson.Point
            coordenadas del punto de la direccion
    """
    location = None
    intentos = 0
    maxIntentos = 5
    while location is None and intentos < maxIntentos:
        intentos += 1
        try:
            time.sleep(1)
            #TODO
            # Es necesario proporcionar un user_agent para utilizar la API
            # Utilizar un nombre aleatorio para el user_agent
            location = Nominatim(user_agent="asdfasdfasdf").geocode(address) # location vale None si no se ha encontrado la dirección, en caso contrario, valdrá un objeto de geopy
        except GeocoderTimedOut:
            # Puede lanzar una excepcion si se supera el tiempo de espera
            # Volver a intentarlo
            continue
    #TODO
    # Devolver un GeoJSON de tipo punto con la latitud y longitud almacenadas.
    # Si no se consiguieron coordenadas, lanzar ValueError: la funcion no puede
    # devolver un punto inventado ni None silenciosamente. Es lo que espera la
    # prueba test_get_location_point_timeout_failure.

    # Comprobamos que se hayan obtenido las coordenadas
    if location is None:
        raise ValueError("No se pudieron obtener coordenadas")

    # Devolvemos la ubicación como un punto GeoJSON (forma estándar de representar una ubicación geográfica mediante sus coordenadas longitud y latitud)
    return Point((location.longitude, location.latitude))

class Model:
    """ 
    Clase de modelo abstracta
    Crear tantas clases que hereden de esta clase como  
    colecciones/modelos se deseen tener en la base de datos.

    Attributes
    ----------
        required_vars : set[str]
            conjunto de atributos requeridos por el modelo
        admissible_vars : set[str]
            conjunto de atributos admitidos por el modelo
        db : pymongo.collection.Collection
            conexion a la coleccion de la base de datos
    
    Methods
    -------
        __setattr__(name: str, value: str | dict) -> None
            Sobreescribe el metodo de asignacion de valores a los 
            atributos del objeto con el fin de controlar qué atributos 
            son modificados y cuando son modificados.
        __getattr__(name: str) -> Any
            Sobreescribe el metodo de acceso a atributos del objeto 
        save()  -> None
            Guarda el modelo en la base de datos
        delete() -> None
            Elimina el modelo de la base de datos
        find(filter: dict[str, str | dict]) -> ModelCursor
            Realiza una consulta de lectura en la BBDD.
            Devuelve un cursor de modelos ModelCursor
        aggregate(pipeline: list[dict]) -> pymongo.command_cursor.CommandCursor
            Devuelve el resultado de una consulta aggregate.
        find_by_id(id: str) -> dict | None
            Busca un documento por su id utilizando la cache y lo devuelve.
            Si no se encuentra el documento, devuelve None.
        init_class(db_collection: pymongo.collection.Collection, required_vars: set[str], admissible_vars: set[str]) -> None
            Inicializa las variables de clase en la inicializacion del sistema.

    """
    _required_vars: set[str]
    _admissible_vars: set[str]
    _location_var: str | None = None
    _db: pymongo.collection.Collection
    _internal_vars: set[str] = frozenset(('_modified_vars', '_required_vars', '_admissible_vars', '_db', '_data', '_location_var'))

    def __init__(self, **kwargs: dict[str, str | dict | list]) -> None:
        """
        Inicializa el modelo con los valores proporcionados en kwargs
        Comprueba que los valores proporcionados en kwargs son admitidos
        por el modelo y que las atributos requeridos son proporcionadas.

        Parameters
        ----------
            kwargs : dict[str, str | dict]
                diccionario con los valores de las atributos del modelo
        """
        # Creamos el atributo privado que guarda los atributos modificados
        self._modified_vars = set()

        self._data: dict[str, str | dict | list] = {}
        #TODO
        # Realizar las comprabociones y gestiones necesarias
        # antes de la asignacion.

        # Comprueba lo sigueinte
        # 1. "Todos los atributos que me han enviado están entre los atributos permitidos + obligatorios."
        # 2. "¿Todos los atributos obligatorios están entre los atributos recibidos?"
        
        if (not set(kwargs).issubset(self._admissible_vars.union(self._required_vars))) or \
            (not self._required_vars.issubset(set(kwargs))):
            raise AttributeError("[-] Los atributos ingresados no son compatible con el modelo")

        # Asigna todos los valores en kwargs a las atributos con 
        # nombre las claves en kwargs
        # Utilizamos el atributo data para guardar los variables 
        # almacenadas en la base de datos en una solo atributo
        # Encapsular los datos en una sola variable facilita la 
        # gestion en metodos como save.
        self._data.update(kwargs)

    def __setattr__(self, name: str, value: str | dict) -> None:
        """ Sobreescribe el metodo de asignacion de valores a los 
        atributos del objeto con el fin de controlar que atributos 
        son modificados y cuando son modificados.
        """
        if name in self._internal_vars:
            super().__setattr__(name, value)
            return
        #TODO
        # Realizar las comprabociones y gestiones necesarias
        # antes de la asignacion.
        # Comprobamos que name sea una variable interna
    
        # Comprobamos que el atributo 'name' esté entre los atributos admisibles y obligatorios del modelo
        if name not in self._admissible_vars.union(self._required_vars):
            return

        # Guardamos la variable que ha sido modificada  
        self._modified_vars.add(name)

        # Asigna el valor value a la variable name
        self._data[name] = value

    def __getattr__(self, name: str) -> Any:
        """ Sobreescribe el metodo de acceso a atributos del objeto
        __getattr__ solo es llamado cuando no encuentra el atributo
        en el objeto 
        """
        if name in self._internal_vars:
            return super().__getattribute__(name)
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError

    def save(self) -> None:
        """
        Guarda el modelo en la base de datos
        Si el modelo no existe en la base de datos, se crea un nuevo
        documento con los valores del modelo. En caso contrario, se
        actualiza el documento existente con los nuevos valores del
        modelo.
        """
        #TODO
        if "_id" not in self._data:

            # Comprobamos que el usuario haya guardado una localización
            if (self._location_var in self._data):
                self._data[f"{self._location_var}_loc"] = getLocationPoint(self._data[self._location_var])

            # MongoDB genera un _id automáticamente, lo guardamos para poder usarlo después
            id_mongo = self._db.insert_one(self._data)
            self._data["_id"] = id_mongo.inserted_id
        else: # entra si se ha guardado el documento en la base de datos
            cambios = {}

            for variable in self._modified_vars:
                cambios[variable] = self._data[variable]

            # Comprobamos que location var exista y que el usuario haya guardado una localización
            if (self._location_var in self._data) and (self._location_var in cambios):
                cambios[f"{self._location_var}_loc"] = getLocationPoint(self._data[self._location_var])

            self._db.update_one(
                {"_id": self._data["_id"]},
                {"$set": cambios}
            )

        # Ya hemos guardado los cambios por lo que limpiamos la lista de atributos modificados
        self._modified_vars.clear()



    def delete(self) -> None:
        """
        Elimina el modelo de la base de datos
        """
        #TODO
        self._db.delete_one({"_id":self._data["_id"]})
    
    @classmethod
    def find(cls, filter: dict[str, str | dict]) -> Any:
        """ 
        Utiliza el metodo find de pymongo para realizar una consulta
        de lectura en la BBDD.
        find debe devolver un cursor de modelos ModelCursor

        Parameters
        ----------
            filter : dict[str, str | dict]
                diccionario con el criterio de busqueda de la consulta
        Returns
        -------
            ModelCursor
                cursor de modelos
        """ 
        #TODO
        # cls es el puntero a la clase
        #No olvidar eliminar esta linea una vez implementado

        # Uso el find de pymongo con el filtro
        return ModelCursor(cls, cls._db.find(filter))

    @classmethod
    def aggregate(cls, pipeline: list[dict]) -> pymongo.command_cursor.CommandCursor:
        """ 
        Devuelve el resultado de una consulta aggregate. 
        No hay nada que hacer en esta funcion.
        Se utilizara para las consultas solicitadas
        en el segundo proyecto de la practica.

        Parameters
        ----------
            pipeline : list[dict]
                lista de etapas de la consulta aggregate 
        Returns
        -------
            pymongo.command_cursor.CommandCursor
                cursor de pymongo con el resultado de la consulta
        """ 
        return cls._db.aggregate(pipeline)
    
    @classmethod
    def find_by_id(cls, id: str) -> Self | None:
        """ 
        NO IMPLEMENTAR HASTA EL TERCER PROYECTO
        Busca un documento por su id utilizando la cache y lo devuelve.
        Si no se encuentra el documento, devuelve None.

        Parameters
        ----------
            id : str
                id del documento a buscar
        Returns
        -------
            Self | None
                Modelo del documento encontrado o None si no se encuentra
        """ 
        #TODO
        pass

    @classmethod
    def init_class(cls, db_collection: pymongo.collection.Collection, indexes:dict[str,str], required_vars: set[str], admissible_vars: set[str]) -> None:
        """ 
        Inicializa los atributos de clase en la inicializacion del sistema.
        Aqui se deben inicializar o asegurar los indices. Tambien se puede
        alguna otra inicialización/comprobaciones o cambios adicionales
        que estime el alumno.

        Parameters
        ----------
            db_collection : pymongo.collection.Collection
                Conexion a la collecion de la base de datos.
            indexes: Dict[str,str]
                Set de indices y tipo de indices para la coleccion
            required_vars : set[str]
                Set de atributos requeridos por el modelo
            admissible_vars : set[str] 
                Set de atributos admitidos por el modelo
        """
        # Añadimos un ID a las variables admitidas, esto nos permitirá en save saber si existe el documento en la base de datos
        admissible_vars.add("_id")

        cls._db = db_collection
        cls._required_vars = required_vars
        cls._admissible_vars = admissible_vars
        # TODO
        # Recorrer indexes y crear cada índice segun su tipo: 'unique', 'asc'
        # y 'geosphere'. Comparar el tipo por igualdad, no con el operador 'in'.
        # 
        # Preguntar al profesor de que va esto.
        # Ojo con el índice geoespacial: save() guarda el GeoJSON Point en
        # <campo>_loc, luego el índice 2dsphere va sobre <campo>_loc, mientras
        # que _location_var debe guardar el nombre del campo base.

        for key, value in indexes.items():
            if value == "unique":
                cls._db.create_index([(key, 1)], unique=True)
            elif value == "asc":
                cls._db.create_index([(key, 1)])
            elif value == "geosphere":
                cls._db.create_index([(f"{key}_loc", pymongo.GEOSPHERE)])
                cls._location_var = key
                admissible_vars.add(f"{key}_loc")


class ModelCursor:
    """ 
    Cursor para iterar sobre los documentos del resultado de una
    consulta. Los documentos deben ser devueltos en forma de objetos
    modelo.

    Attributes
    ----------
        model_class : Model
            Clase para crear los modelos de los documentos que se iteran.
        cursor : pymongo.cursor.Cursor
            Cursor de pymongo a iterar

    Methods
    -------
        __iter__() -> Generator
            Devuelve un iterador que recorre los elementos del cursor
            y devuelve los documentos en forma de objetos modelo.
    """

    def __init__(self, model_class: Model, cursor: pymongo.cursor.Cursor):
        """
        Inicializa el cursor con la clase de modelo y el cursor de pymongo

        Parameters
        ----------
            model_class : Model
                Clase para crear los modelos de los documentos que se iteran.
            cursor: pymongo.cursor.Cursor
                Cursor de pymongo a iterar
        """
        self.model = model_class
        self.cursor = cursor
    
    def __iter__(self) -> Generator:
        """
        Devuelve un iterador que recorre los elementos del cursor
        y devuelve los documentos en forma de objetos modelo.
        Utilizar yield para generar el iterador
        Utilizar la funcion next para obtener el siguiente documento del cursor
        Utilizar alive para comprobar si existen mas documentos.
        """
        #TODO
        #No olvidar eliminar esta linea una vez implementado

        while self.cursor.alive: # Mientras tenga documentos pendientes
            try:
                documento = next(self.cursor)
                yield self.model(**documento) # ** lo pasa como kwargs al modelo
            except StopIteration:
                break

def initApp(definitions_path: str = "./models.yml", mongodb_uri="mongodb://localhost:27017/", db_name="abd", scope=globals()) -> None:
    """ 
    Declara las clases que heredan de Model para cada uno de los 
    modelos de las colecciones definidas en definitions_path.
    Inicializa las clases de los modelos proporcionando los indices y 
    atributos admitidos y requeridos para cada una de ellas y la conexión a la
    collecion de la base de datos.
    
    Parameters
    ----------
        definitions_path : str
            ruta al fichero de definiciones de modelos
        mongodb_uri : str
            uri de conexion a la base de datos
        db_name : str
            nombre de la base de datos
    """
    #TODO
    # Inicializar base de datos

    client = MongoClient(mongodb_uri) #Conectar al servidor local
    db = client[db_name] # Inicializo la base de datos

    #TODO
    # Declarar tantas clases modelo colecciones existan en la base de datos
    # Leer el fichero de definiciones de modelos para obtener las colecciones,
    # indices y los atributos admitidos y requeridos para cada una de ellas.
    # Ejemplo de declaracion de modelo para colecion llamada MiModelo
    #  scope["MiModelo"] = type("MiModelo", (Model,),{})
    # La clase se declara en tiempo de ejecucion y queda en scope, que no tiene
    # por que ser el espacio de nombres global: las pruebas le pasan su propio
    # diccionario. Por eso se inicializa a traves de scope y no por su nombre,
    # que ahi todavia no existe.
    #  scope["MiModelo"].init_class(db_collection=None, indexes=None, required_vars=None, admissible_vars=None)
     
    with open(definitions_path, "r") as fichero: #Lee el fichero
        diccionario = yaml.safe_load(fichero) # Lo combierto a dict

    for clave, valor in diccionario.items(): # Bucle que recorre el fichero

        scope[clave] = type(clave, (Model,), {}) # Declaracion del modelo

        # Diccionario de indices.
        indices: dict[str, str] = {}

        for val in valor.get("unique_indexes") or []: # Evita errores en caso vacio
            indices[val] = "unique"

        for val in valor.get("regular_indexes") or []:
            indices[val] = "asc"

        direccion = valor.get("location_index")
        if direccion:
            indices[direccion] = "geosphere"

        # Inicializa la clase
        scope[clave].init_class(
            db_collection=db[clave],
            indexes=indices,
            required_vars=set(valor["required_vars"]),
            admissible_vars=set(valor["admissible_vars"])
        )

'''
No hemos añadido ninguna documento a las colecciones ya que ingresamos directamente los datos en tiempo de ejecución para siumalr como sería el funcionamiento en una producción real
'''
if __name__ == '__main__':

    # ============================================================
    # INICIALIZACIÓN
    # ============================================================

    initApp()

    print("\n" + "=" * 60)
    print("INICIO DE PRUEBAS")
    print("=" * 60)


    # ============================================================
    # RECINTO
    # ============================================================

    print("\n" + "-" * 60)
    print("PRUEBAS DE RECINTO")
    print("-" * 60)


    # ============================================================
    # PRUEBA 1 - CREACIÓN CORRECTA
    # ============================================================

    print("\n[1] Creación de Recinto")

    r = Recinto(
        nombre="recinto-test",
        direccion="Calle de Jorge Juan, 99, Madrid, España",
        aforo=6700,
        zona={
            "A": 6000,
            "B": 700
        },
        servicios=["parking", "bar"]
    )

    print("Nombre:", r.nombre)
    print("Dirección:", r.direccion)
    print("Aforo:", r.aforo)
    print("Zona:", r.zona)
    print("Servicios:", r.servicios)

    if (
        r.nombre == "recinto-test"
        and r.direccion == "Calle de Jorge Juan, 99, Madrid, España"
        and r.aforo == 6700
        and r.zona == {"A": 6000, "B": 700}
    ):
        print("OK -> Recinto creado correctamente")
    else:
        print("ERROR -> datos incorrectos")


    # ============================================================
    # PRUEBA 2 - ATRIBUTO NO ADMITIDO
    # ============================================================

    print("\n[2] Atributo no admitido")

    r.color = "rojo"

    if "color" not in r._data:
        print("OK -> atributo no admitido ignorado")
    else:
        print("ERROR -> atributo no admitido almacenado")


    # ============================================================
    # PRUEBA 3 - MODIFICACIÓN DE ATRIBUTO
    # ============================================================

    print("\n[3] Modificación de atributo")

    r.aforo = 7000

    print("Aforo:", r.aforo)
    print("Modificaciones:", r._modified_vars)

    if r._modified_vars == {"aforo"}:
        print("OK -> aforo marcado como modificado")
    else:
        print("ERROR -> modificaciones incorrectas")


    # ============================================================
    # PRUEBA 4 - MODIFICACIÓN DE VARIOS ATRIBUTOS
    # ============================================================

    print("\n[4] Modificación de varios atributos")

    r.nombre = "recinto-test-2"
    r.zona = {
        "A": 5000,
        "B": 2000
    }

    print("Modificaciones:", r._modified_vars)

    if r._modified_vars == {"aforo", "nombre", "zona"}:
        print("OK -> modificaciones correctas")
    else:
        print("ERROR -> modificaciones incorrectas")


    # ============================================================
    # PRUEBA 5 - SAVE
    # ============================================================

    print("\n[5] Guardar Recinto")

    r.save()

    print("ID:", r._data["_id"])
    print("Datos:", r._data)

    if "_id" in r._data:
        print("OK -> documento insertado")
    else:
        print("ERROR -> no se generó _id")

    if len(r._modified_vars) == 0:
        print("OK -> modificaciones limpiadas")
    else:
        print("ERROR -> modificaciones no limpiadas")


    # ============================================================
    # PRUEBA 6 - GEOJSON
    # ============================================================

    print("\n[6] Comprobar GeoJSON")

    if "direccion_loc" in r._data:

        punto = r._data["direccion_loc"]

        print("Punto:", punto)
        print("Tipo:", punto["type"])
        print("Coordenadas:", punto["coordinates"])

        if punto["type"] == "Point":
            print("OK -> es un Point")
        else:
            print("ERROR -> no es un Point")

        if len(punto["coordinates"]) == 2:
            print("Longitud:", punto["coordinates"][0])
            print("Latitud:", punto["coordinates"][1])
            print("OK -> coordenadas correctas")
        else:
            print("ERROR -> número de coordenadas incorrecto")

    else:
        print("ERROR -> no existe direccion_loc")


    # ============================================================
    # PRUEBA 7 - ACTUALIZACIÓN PARCIAL
    # ============================================================

    print("\n[7] Actualización parcial")

    r.aforo = 8000

    print("Modificaciones antes de save():", r._modified_vars)

    if r._modified_vars == {"aforo"}:
        print("OK -> solo aforo será actualizado")
    else:
        print("ERROR -> modificaciones incorrectas")

    r.save()

    if len(r._modified_vars) == 0:
        print("OK -> modificaciones limpiadas")
    else:
        print("ERROR -> modificaciones no limpiadas")


    # ============================================================
    # PRUEBA 8 - ACTUALIZACIÓN DE DIRECCIÓN
    # ============================================================

    print("\n[8] Actualización de dirección")

    r.direccion = "Avenida de Concha Espina, 1, Madrid, España"

    print("Nueva dirección:", r.direccion)
    print("Modificaciones:", r._modified_vars)

    if r._modified_vars == {"direccion"}:
        print("OK -> dirección marcada como modificada")
    else:
        print("ERROR -> modificaciones incorrectas")

    r.save()


    # ============================================================
    # PRUEBA 9 - FIND
    # ============================================================

    print("\n[9] find()")

    cursor = Recinto.find({
        "nombre": "recinto-test-2"
    })

    encontrado = next(iter(cursor), None)

    if encontrado is not None:
        print("OK -> Recinto encontrado")
        print("Nombre:", encontrado.nombre)
        print("Aforo:", encontrado.aforo)
        print("Dirección:", encontrado.direccion)
    else:
        print("ERROR -> Recinto no encontrado")


    # ============================================================
    # PRUEBA 10 - FIND DEVUELVE MODELO
    # ============================================================

    print("\n[10] Tipo devuelto por find()")

    if isinstance(encontrado, Recinto):
        print("OK -> find() devuelve un Recinto")
    else:
        print("ERROR -> find() no devuelve un Recinto")


    # ============================================================
    # PRUEBA 11 - MODIFICAR OBJETO OBTENIDO CON FIND
    # ============================================================

    print("\n[11] Modificar objeto obtenido con find()")

    encontrado.aforo = 9000

    print("Aforo:", encontrado.aforo)
    print("Modificaciones:", encontrado._modified_vars)

    if encontrado._modified_vars == {"aforo"}:
        print("OK -> aforo marcado")
    else:
        print("ERROR -> modificaciones incorrectas")

    encontrado.save()


    # ============================================================
    # PRUEBA 12 - ATRIBUTOS OBLIGATORIOS
    # ============================================================

    print("\n[12] Atributos obligatorios de Recinto")

    try:

        Recinto(
            nombre="recinto-error",
            direccion="Madrid",
            aforo=1000
        )

        print("ERROR -> se permitió crear Recinto sin zona")

    except AttributeError:
        print("OK -> se rechazó Recinto sin zona")


    # ============================================================
    # PRUEBA 13 - ATRIBUTO DESCONOCIDO EN CONSTRUCTOR
    # ============================================================

    print("\n[13] Atributo desconocido en constructor")

    try:

        Recinto(
            nombre="recinto-error",
            direccion="Madrid",
            aforo=1000,
            zona={"A": 1000},
            color="rojo"
        )

        print("ERROR -> se permitió atributo desconocido")

    except AttributeError:
        print("OK -> se rechazó atributo desconocido")


    # ============================================================
    # ARTISTA
    # ============================================================

    print("\n" + "-" * 60)
    print("PRUEBAS DE ARTISTA")
    print("-" * 60)


    # ============================================================
    # PRUEBA 14 - CREACIÓN CORRECTA
    # ============================================================

    print("\n[14] Creación de Artista")

    artista = Artista(
        nombre="Artista Test",
        genero="Rock",
        age=2020,
        pais="España"
    )

    print("Nombre:", artista.nombre)
    print("Género:", artista.genero)
    print("Año:", artista.age)
    print("País:", artista.pais)

    if (
        artista.nombre == "Artista Test"
        and artista.genero == "Rock"
        and artista.age == 2020
        and artista.pais == "España"
    ):
        print("OK -> Artista creado correctamente")
    else:
        print("ERROR -> datos incorrectos")


    # ============================================================
    # PRUEBA 15 - ATRIBUTO NO ADMITIDO
    # ============================================================

    print("\n[15] Atributo no admitido en Artista")

    artista.color = "rojo"

    if "color" not in artista._data:
        print("OK -> atributo no admitido ignorado")
    else:
        print("ERROR -> atributo no admitido almacenado")


    # ============================================================
    # PRUEBA 16 - MODIFICACIÓN
    # ============================================================

    print("\n[16] Modificación de Artista")

    artista.genero = "Pop"

    print("Género:", artista.genero)
    print("Modificaciones:", artista._modified_vars)

    if artista._modified_vars == {"genero"}:
        print("OK -> género marcado como modificado")
    else:
        print("ERROR -> modificaciones incorrectas")


    # ============================================================
    # PRUEBA 17 - SAVE
    # ============================================================

    print("\n[17] Guardar Artista")

    artista.save()

    print("ID:", artista._data["_id"])
    print("Datos:", artista._data)

    if "_id" in artista._data:
        print("OK -> Artista insertado")
    else:
        print("ERROR -> Artista no insertado")

    if len(artista._modified_vars) == 0:
        print("OK -> modificaciones limpiadas")
    else:
        print("ERROR -> modificaciones no limpiadas")


    # ============================================================
    # PRUEBA 18 - FIND DE ARTISTA
    # ============================================================

    print("\n[18] find() de Artista")

    cursor_artista = Artista.find({
        "nombre": "Artista Test"
    })

    artista_encontrado = next(iter(cursor_artista), None)

    if artista_encontrado is not None:
        print("OK -> Artista encontrado")
        print("Nombre:", artista_encontrado.nombre)
        print("Género:", artista_encontrado.genero)
        print("País:", artista_encontrado.pais)
    else:
        print("ERROR -> Artista no encontrado")


    # ============================================================
    # PRUEBA 19 - FIND DEVUELVE MODELO
    # ============================================================

    print("\n[19] Tipo devuelto por find()")

    if isinstance(artista_encontrado, Artista):
        print("OK -> find() devuelve un Artista")
    else:
        print("ERROR -> find() no devuelve un Artista")


    # ============================================================
    # PRUEBA 20 - ATRIBUTOS OBLIGATORIOS DE ARTISTA
    # ============================================================

    print("\n[20] Atributos obligatorios de Artista")

    try:

        Artista(
            nombre="Artista Incorrecto"
        )

        print("ERROR -> se permitió Artista sin género")

    except AttributeError:
        print("OK -> se rechazó Artista sin género")


    # ============================================================
    # PRUEBA 21 - ATRIBUTO DESCONOCIDO EN CONSTRUCTOR
    # ============================================================

    print("\n[21] Atributo desconocido en Artista")

    try:

        Artista(
            nombre="Artista Incorrecto",
            genero="Rock",
            color="rojo"
        )

        print("ERROR -> se permitió atributo desconocido")

    except AttributeError:
        print("OK -> se rechazó atributo desconocido")


    # ============================================================
    # PRUEBA 22 - AGGREGATE
    # ============================================================

    print("\n[22] aggregate()")

    resultados = list(Artista.aggregate([
        {
            "$match": {
                "nombre": "Artista Test"
            }
        }
    ]))

    print("Resultados:", resultados)

    if len(resultados) > 0:
        print("OK -> aggregate() devuelve resultados")
    else:
        print("ERROR -> aggregate() no devuelve resultados")


    # ============================================================
    # PRUEBA 23 - DELETE RECINTO
    # ============================================================

    print("\n[23] delete() de Recinto")

    id_recinto = r._data["_id"]

    r.delete()

    comprobacion = Recinto.find({
        "_id": id_recinto
    })

    eliminado = next(iter(comprobacion), None)

    if eliminado is None:
        print("OK -> Recinto eliminado correctamente")
    else:
        print("ERROR -> Recinto no eliminado")


    # ============================================================
    # PRUEBA 24 - DELETE ARTISTA
    # ============================================================

    print("\n[24] delete() de Artista")

    id_artista = artista._data["_id"]

    artista.delete()

    comprobacion = Artista.find({
        "_id": id_artista
    })

    eliminado = next(iter(comprobacion), None)

    if eliminado is None:
        print("OK -> Artista eliminado correctamente")
    else:
        print("ERROR -> Artista no eliminado")


    # ============================================================
    # FIN
    # ============================================================

    print("\n" + "=" * 60)
    print("FIN DE TODAS LAS PRUEBAS")
    print("=" * 60)