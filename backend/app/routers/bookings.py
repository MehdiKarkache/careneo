import uuid

from app import schemas
from app.deps import ALL_ROLES, CurrentUser, SessionDep, allow
from app.domain import BookingStatus, Role
from app.routers import api_router
from app.usecases import bookings

router = api_router("Réservations")


@router.get(
    "/bookings",
    operation_id="listBookings",
    summary="Lister les réservations visibles par l'utilisateur",
    **allow(*ALL_ROLES),
)
async def list_bookings(
    user: CurrentUser, session: SessionDep, status: BookingStatus | None = None
) -> list[schemas.Booking]:
    visible = await bookings.list_bookings(session, user, status)
    return [schemas.Booking.from_model(booking) for booking in visible]


@router.post(
    "/bookings",
    operation_id="createBooking",
    summary="Envoyer une demande de réservation",
    status_code=201,
    **allow(Role.OWNER),
)
async def create_booking(
    body: schemas.BookingInput, user: CurrentUser, session: SessionDep
) -> schemas.Booking:
    booking_id = await bookings.create_booking(
        session,
        user,
        vessel_id=body.vessel_id,
        slot_id=body.slot_id,
        service_ids=body.service_ids,
        message=body.message,
    )
    return schemas.Booking.from_model(await bookings.get_booking(session, user, booking_id))


@router.get(
    "/bookings/{id}",
    operation_id="getBooking",
    summary="Détail d'une réservation et son historique",
    **allow(*ALL_ROLES),
)
async def get_booking(
    id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> schemas.BookingDetail:
    booking = await bookings.get_booking(session, user, id, with_events=True)
    return schemas.BookingDetail.from_model(booking)


@router.post(
    "/bookings/{id}/accept",
    operation_id="acceptBooking",
    summary="Accepter une demande",
    **allow(Role.YARD),
)
async def accept_booking(id: uuid.UUID, user: CurrentUser, session: SessionDep) -> schemas.Booking:
    await bookings.accept_booking(session, user, id)
    return schemas.Booking.from_model(await bookings.get_booking(session, user, id))


@router.post(
    "/bookings/{id}/reject",
    operation_id="rejectBooking",
    summary="Refuser une demande avec un motif",
    **allow(Role.YARD),
)
async def reject_booking(
    id: uuid.UUID, body: schemas.RejectInput, user: CurrentUser, session: SessionDep
) -> schemas.Booking:
    await bookings.reject_booking(session, user, id, body.reason)
    return schemas.Booking.from_model(await bookings.get_booking(session, user, id))


@router.post(
    "/bookings/{id}/cancel",
    operation_id="cancelBooking",
    summary="Annuler ma demande en attente",
    **allow(Role.OWNER),
)
async def cancel_booking(id: uuid.UUID, user: CurrentUser, session: SessionDep) -> schemas.Booking:
    await bookings.cancel_booking(session, user, id)
    return schemas.Booking.from_model(await bookings.get_booking(session, user, id))
